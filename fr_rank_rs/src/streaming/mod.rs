// src/streaming/mod.rs
// ===================================================================
// Потоковый процессор Magnus.
//
// Поддерживает:
// - path_length и degree
// - window_size: периодический reset rank_tracker
// - overlap: нахлёст между окнами
// - flush: принудительное закрытие хвостового окна
// - process_batch_no_results: batch без аллокации результатов
// - fast_layer: физические триггеры по датчикам (опционально)
// ===================================================================

pub mod rank_tracker;
pub mod quantizer;
pub mod state_graph;
pub mod magnus_expansion;
pub mod fast_layer;

use rank_tracker::RankTracker;
use quantizer::AdaptiveQuantizer;
use state_graph::StateGraph;
use magnus_expansion::MagnusExpansion;
use fast_layer::FastLayer;


// ================================================================
// ОТПЕЧАТОК ОКНА
// ================================================================

#[derive(Debug, Clone, Default)]
pub struct WindowFingerprint {
    pub t_start: usize,
    pub t_end: usize,
    pub n_points: usize,
    pub rank: usize,
    pub n_states: usize,
    pub n_words: usize,
    pub n_transitions: usize,
    pub is_partial: bool,
    pub is_tail: bool,
}


// ================================================================
// РЕЗУЛЬТАТ
// ================================================================

#[derive(Debug, Clone)]
pub struct StreamingResult {
    pub t: usize,
    pub state_id: usize,
    pub n_states: usize,
    pub n_transitions: usize,
    pub n_words: usize,
    pub rank: usize,
    pub rank_increased: bool,
    pub n_new_words: usize,
    pub window_closed: bool,
    /// Триггеры FAST-уровня на этой точке (пусто если выключен).
    pub fast_triggers: usize,
}


#[derive(Debug, Clone)]
pub struct Metrics {
    pub t: usize,
    pub n_states: usize,
    pub n_transitions: usize,
    pub n_words: usize,
    pub rank: usize,
    pub n_rows_added: usize,
    pub n_windows_closed: usize,
    pub fast_n_triggers: usize,
}


// ================================================================
// ПРОЦЕССОР
// ================================================================

pub struct StreamingProcessor {
    quantizer: AdaptiveQuantizer,
    state_graph: StateGraph,
    rank_tracker: RankTracker,
    magnus: MagnusExpansion,
    n_sensors: usize,
    p: u64,
    degree: usize,
    path_length: usize,
    t: usize,
    n_rows_added: usize,

    // Оконная логика
    window_size: usize,
    overlap: usize,
    points_in_window: usize,
    t_window_start: usize,
    n_windows_closed: usize,
    window_fingerprints: Vec<WindowFingerprint>,

    // FAST-уровень (опционально)
    fast_layer: Option<FastLayer>,
    fast_enabled: bool,
}


impl StreamingProcessor {
    pub fn new(
        n_sensors: usize,
        alpha: f64,
        n_sigma: f64,
        min_count: usize,
        p: u64,
        degree: usize,
        path_length: usize,
        window_size: usize,
        overlap: usize,
        // FAST-уровень
        enable_fast: bool,
        fast_alpha: f64,
        fast_z_threshold: f64,
    ) -> Self {
        assert!(n_sensors > 0);
        assert!(alpha > 0.0 && alpha <= 1.0);
        assert!(n_sigma > 0.0);
        assert!(min_count >= 1);
        assert!(degree >= 1);
        assert!(p >= 3);
        assert!(
            path_length == 0 || path_length >= 2,
            "path_length должен быть 0 (auto) или >= 2"
        );

        let effective_path_length = if path_length == 0 {
            degree + 1
        } else {
            path_length.max(degree + 1)
        };
        assert!(effective_path_length >= 2);

        if window_size > 0 {
            assert!(
                overlap < window_size,
                "overlap ({}) должен быть < window_size ({})",
                overlap, window_size
            );
        }

        let fast_layer = if enable_fast {
            assert!(fast_alpha > 0.0 && fast_alpha <= 1.0);
            assert!(fast_z_threshold > 0.0);
            Some(FastLayer::new(n_sensors, fast_alpha, fast_z_threshold))
        } else {
            None
        };

        Self {
            quantizer: AdaptiveQuantizer::new(n_sensors, alpha, n_sigma),
            state_graph: StateGraph::new(min_count, effective_path_length),
            rank_tracker: RankTracker::with_degree_hint(p, degree),
            magnus: MagnusExpansion::new(degree, p),
            n_sensors,
            p,
            degree,
            path_length: effective_path_length,
            t: 0,
            n_rows_added: 0,
            window_size,
            overlap,
            points_in_window: 0,
            t_window_start: 0,
            n_windows_closed: 0,
            window_fingerprints: Vec::new(),
            fast_layer,
            fast_enabled: enable_fast,
        }
    }


    pub fn process(&mut self, x: &[f64]) -> StreamingResult {
        assert_eq!(x.len(), self.n_sensors);

        self.t += 1;
        self.points_in_window += 1;

        // 0. FAST-уровень (если включён) — параллельно, ДО графа
        let n_fast_triggers = if let Some(ref mut fast) = self.fast_layer {
            fast.update(x, self.t).len()
        } else {
            0
        };

        // 1. Квантование
        let state = self.quantizer.quantize(x);

        // 2. Граф
        let (state_id, new_words) = self.state_graph.add_state(state);

        // 3. Magnus + rank
        let mut rank_increased = false;
        let n_new_words = new_words.len();

        for word in &new_words {
            let k = self.state_graph.n_states();
            let row = self.magnus.build_word_row(word, k);
            if self.rank_tracker.add_row(row) {
                rank_increased = true;
                self.n_rows_added += 1;
            }
        }

        // 4. Закрытие окна
        let mut window_closed = false;

        if self.window_size > 0 && self.points_in_window >= self.window_size {
            self.close_window(false, false);
            window_closed = true;
        }

        StreamingResult {
            t: self.t,
            state_id,
            n_states: self.state_graph.n_states(),
            n_transitions: self.state_graph.n_transitions(),
            n_words: self.state_graph.n_words(),
            rank: self.rank_tracker.rank(),
            rank_increased,
            n_new_words,
            window_closed,
            fast_triggers: n_fast_triggers,
        }
    }


    /// БЫСТРАЯ обработка batch — БЕЗ аллокации Vec<StreamingResult>.
    pub fn process_batch_no_results(
        &mut self,
        x: &[f64],
        n_sensors: usize,
    ) -> StreamingResult {
        assert_eq!(n_sensors, self.n_sensors);
        assert_eq!(x.len() % n_sensors, 0);

        let n_points = x.len() / n_sensors;

        let mut last = StreamingResult {
            t: self.t,
            state_id: 0,
            n_states: self.state_graph.n_states(),
            n_transitions: self.state_graph.n_transitions(),
            n_words: self.state_graph.n_words(),
            rank: self.rank_tracker.rank(),
            rank_increased: false,
            n_new_words: 0,
            window_closed: false,
            fast_triggers: 0,
        };

        for i in 0..n_points {
            let start = i * n_sensors;
            let end = start + n_sensors;
            last = self.process(&x[start..end]);
        }

        last
    }


    /// Обычная batch-обработка (с Vec).
    pub fn process_batch(&mut self, x: &[f64], n_sensors: usize) -> Vec<StreamingResult> {
        assert_eq!(n_sensors, self.n_sensors);
        assert_eq!(x.len() % n_sensors, 0);

        let n_points = x.len() / n_sensors;
        let mut results = Vec::with_capacity(n_points);

        for i in 0..n_points {
            let start = i * n_sensors;
            let end = start + n_sensors;
            results.push(self.process(&x[start..end]));
        }

        results
    }


    /// Принудительно закрывает хвостовое окно.
    pub fn flush(&mut self) -> bool {
        if self.points_in_window > 0 {
            let is_partial = self.points_in_window < self.window_size;
            self.close_window(is_partial, true);
            return true;
        }
        false
    }


    fn close_window(&mut self, is_partial: bool, is_tail: bool) {
        let fp = WindowFingerprint {
            t_start: self.t_window_start,
            t_end: self.t,
            n_points: self.points_in_window,
            rank: self.rank_tracker.rank(),
            n_states: self.state_graph.n_states(),
            n_words: self.state_graph.n_words(),
            n_transitions: self.state_graph.n_transitions(),
            is_partial,
            is_tail,
        };
        self.window_fingerprints.push(fp);
        self.n_windows_closed += 1;

        let keep = self.overlap.max(self.path_length - 1);
        self.state_graph.soft_reset(keep);
        self.rank_tracker.reset();

        self.n_rows_added = 0;
        self.t_window_start = self.t.saturating_sub(self.overlap);
        self.points_in_window = 0;
    }


    pub fn reset(&mut self) {
        self.quantizer.reset();
        self.state_graph.reset();
        self.rank_tracker.reset();
        if let Some(ref mut fast) = self.fast_layer {
            fast.reset();
        }
        self.t = 0;
        self.n_rows_added = 0;
        self.points_in_window = 0;
        self.t_window_start = 0;
        self.n_windows_closed = 0;
        self.window_fingerprints.clear();
    }


    // ============================================================
    // ГЕТТЕРЫ
    // ============================================================

    #[inline] pub fn rank(&self) -> usize { self.rank_tracker.rank() }
    #[inline] pub fn n_states(&self) -> usize { self.state_graph.n_states() }
    #[inline] pub fn n_transitions(&self) -> usize { self.state_graph.n_transitions() }
    #[inline] pub fn n_words(&self) -> usize { self.state_graph.n_words() }
    #[inline] pub fn get_t(&self) -> usize { self.t }
    #[inline] pub fn get_n_sensors(&self) -> usize { self.n_sensors }
    #[inline] pub fn get_p(&self) -> u64 { self.p }
    #[inline] pub fn get_degree(&self) -> usize { self.degree }
    #[inline] pub fn get_path_length(&self) -> usize { self.path_length }
    #[inline] pub fn get_window_size(&self) -> usize { self.window_size }
    #[inline] pub fn get_overlap(&self) -> usize { self.overlap }
    #[inline] pub fn n_windows_closed(&self) -> usize { self.n_windows_closed }
    #[inline] pub fn path_len(&self) -> usize { self.state_graph.path_len() }
    #[inline] pub fn fast_enabled(&self) -> bool { self.fast_enabled }

    pub fn window_fingerprints(&self) -> &[WindowFingerprint] {
        &self.window_fingerprints
    }

    pub fn current_window_fingerprint(&self) -> WindowFingerprint {
        WindowFingerprint {
            t_start: self.t_window_start,
            t_end: self.t,
            n_points: self.points_in_window,
            rank: self.rank_tracker.rank(),
            n_states: self.state_graph.n_states(),
            n_words: self.state_graph.n_words(),
            n_transitions: self.state_graph.n_transitions(),
            is_partial: false,
            is_tail: false,
        }
    }

    pub fn metrics(&self) -> Metrics {
        Metrics {
            t: self.t,
            n_states: self.state_graph.n_states(),
            n_transitions: self.state_graph.n_transitions(),
            n_words: self.state_graph.n_words(),
            rank: self.rank_tracker.rank(),
            n_rows_added: self.rank_tracker.n_rows_added(),
            n_windows_closed: self.n_windows_closed,
            fast_n_triggers: self.fast_n_triggers(),
        }
    }

    pub fn relations(&self) -> Vec<(usize, usize)> {
        self.state_graph.get_relations()
    }

    pub fn get_state(&self, id: usize) -> Option<Vec<u8>> {
        self.state_graph.get_state(id).cloned()
    }

    pub fn get_transition_count(&self, from: usize, to: usize) -> usize {
        self.state_graph.get_transition_count(from, to)
    }

    // ============================================================
    // FAST-УРОВЕНЬ
    // ============================================================

    /// Все триггеры: (t, sensor_idx, value, z_score, deviation_pct)
    pub fn fast_triggers(&self) -> Vec<(usize, usize, f64, f64, f64)> {
        self.fast_layer
            .as_ref()
            .map(|fl| {
                fl.triggers()
                    .iter()
                    .map(|tr| {
                        (tr.t, tr.sensor_idx, tr.value, tr.z_score, tr.deviation_pct)
                    })
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn fast_n_triggers(&self) -> usize {
        self.fast_layer.as_ref().map(|fl| fl.n_triggers()).unwrap_or(0)
    }

    pub fn fast_triggers_per_sensor(&self) -> Vec<usize> {
        self.fast_layer
            .as_ref()
            .map(|fl| fl.triggers_per_sensor())
            .unwrap_or_default()
    }

    /// Триггеры FAST-уровня в диапазоне [t_start, t_end).
    pub fn fast_triggers_in_range(
        &self,
        t_start: usize,
        t_end: usize,
    ) -> Vec<(usize, usize, f64, f64, f64)> {
        self.fast_layer
            .as_ref()
            .map(|fl| {
                fl.triggers_in_range(t_start, t_end)
                    .iter()
                    .map(|tr| {
                        (tr.t, tr.sensor_idx, tr.value, tr.z_score, tr.deviation_pct)
                    })
                    .collect()
            })
            .unwrap_or_default()
    }
}


// ================================================================
// ТЕСТЫ
// ================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_no_fast() {
        let proc = StreamingProcessor::new(
            7, 0.05, 1.5, 2, 1_000_000_007, 2, 3, 0, 0,
            false, 0.001, 3.0,
        );
        assert_eq!(proc.rank(), 0);
        assert!(!proc.fast_enabled());
        assert_eq!(proc.fast_n_triggers(), 0);
    }

    #[test]
    fn test_create_with_fast() {
        let proc = StreamingProcessor::new(
            7, 0.05, 1.5, 2, 1_000_000_007, 2, 3, 0, 0,
            true, 0.001, 3.0,
        );
        assert!(proc.fast_enabled());
        assert_eq!(proc.fast_n_triggers(), 0);
    }

    #[test]
    fn test_window_closes() {
        let mut proc = StreamingProcessor::new(
            2, 0.1, 1.0, 2, 1_000_000_007, 3, 4, 100, 0,
            false, 0.001, 3.0,
        );
        let mut n_closed = 0;

        for i in 0..300 {
            let x = [(i as f64 * 0.1).sin(), (i as f64 * 0.1).cos()];
            let r = proc.process(&x);
            if r.window_closed {
                n_closed += 1;
            }
        }

        assert_eq!(n_closed, 3);
    }

    #[test]
    fn test_flush_closes_tail() {
        let mut proc = StreamingProcessor::new(
            2, 0.1, 1.0, 2, 1_000_000_007, 3, 4, 100, 0,
            false, 0.001, 3.0,
        );
        for i in 0..50 {
            let x = [(i as f64 * 0.1).sin(), (i as f64 * 0.1).cos()];
            proc.process(&x);
        }

        assert!(proc.flush());
        assert_eq!(proc.n_windows_closed(), 1);
    }

    #[test]
    fn test_process_batch_no_results() {
        let mut proc = StreamingProcessor::new(
            2, 0.1, 1.0, 2, 1_000_000_007, 3, 4, 100, 10,
            false, 0.001, 3.0,
        );
        let mut data = Vec::with_capacity(500 * 2);
        for i in 0..500 {
            data.push((i as f64 * 0.1).sin());
            data.push((i as f64 * 0.1).cos());
        }

        let result = proc.process_batch_no_results(&data, 2);
        assert_eq!(result.t, 500);
        assert!(result.rank > 0);
    }

    #[test]
    fn test_fast_layer_integration() {
        let mut proc = StreamingProcessor::new(
            2, 0.1, 1.0, 2, 1_000_000_007, 2, 3, 0, 0,
            true, 0.01, 2.0,  // FAST включён
        );

        // Набираем статистику
        for i in 0..200 {
            let x = [
                1.0 + (i as f64 * 0.001).sin() * 0.01,
                1.0 + (i as f64 * 0.001).cos() * 0.01,
            ];
            proc.process(&x);
        }

        let n_before = proc.fast_n_triggers();

        // Резкий скачок
        proc.process(&[10.0, 1.0]);

        let n_after = proc.fast_n_triggers();
        assert!(n_after > n_before, "триггер не сработал");
    }

    #[test]
    fn test_fast_triggers_per_sensor() {
        let mut proc = StreamingProcessor::new(
            3, 0.1, 1.0, 2, 1_000_000_007, 2, 3, 0, 0,
            true, 0.05, 2.0,
        );

        for i in 0..200 {
            proc.process(&[1.0, 1.0, 1.0]);
        }

        // Скачок на 2-м датчике
        proc.process(&[1.0, 20.0, 1.0]);

        let per_sensor = proc.fast_triggers_per_sensor();
        assert_eq!(per_sensor.len(), 3);
        assert!(per_sensor[1] > 0, "должен быть триггер на датчике 1");
    }

    #[test]
    fn test_fast_reset() {
        let mut proc = StreamingProcessor::new(
            2, 0.1, 1.0, 2, 1_000_000_007, 2, 3, 0, 0,
            true, 0.1, 2.0,
        );

        for i in 0..200 {
            proc.process(&[1.0, 1.0]);
        }
        proc.process(&[100.0, 1.0]);
        assert!(proc.fast_n_triggers() > 0);

        proc.reset();
        assert_eq!(proc.fast_n_triggers(), 0);
    }
}