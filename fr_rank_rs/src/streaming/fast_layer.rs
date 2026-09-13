// src/streaming/fast_layer.rs
// ===================================================================
// FAST-уровень: детекция физических триггеров по датчикам.
//
// Идея:
// - EMA (экспоненциальное скользящее среднее) и дисперсия на каждый датчик
// - Z-score: |x - EMA| / std
// - Если |Z| > threshold → триггер
//
// Работает параллельно с основным графом.
// Не знает о rank, states, words.
// ===================================================================

#[derive(Debug, Clone)]
pub struct PhysicsTrigger {
    pub t: usize,
    pub sensor_idx: usize,
    pub value: f64,
    pub ema_mean: f64,
    pub ema_std: f64,
    pub z_score: f64,
    pub deviation_pct: f64,
}


pub struct FastLayer {
    /// EMA среднего на каждый датчик.
    ema_mean: Vec<f64>,
    /// EMA дисперсии на каждый датчик.
    ema_var: Vec<f64>,
    /// Коэффициент EMA.
    alpha: f64,
    /// Порог Z-score (например 3.0 = 3 сигмы).
    z_threshold: f64,
    /// Все триггеры (для анализа).
    triggers: Vec<PhysicsTrigger>,
    /// Сколько точек обработано (для отладки).
    n_processed: usize,
}


impl FastLayer {
    pub fn new(n_sensors: usize, alpha: f64, z_threshold: f64) -> Self {
        assert!(n_sensors > 0);
        assert!(alpha > 0.0 && alpha <= 1.0);
        assert!(z_threshold > 0.0);

        Self {
            ema_mean: vec![0.0; n_sensors],
            ema_var: vec![1e-6; n_sensors],  // избегаем деления на 0
            alpha,
            z_threshold,
            triggers: Vec::new(),
            n_processed: 0,
        }
    }


    /// Обновить состояние на новой точке.
    /// Возвращает список триггеров, сработавших на этой точке.
    pub fn update(&mut self, x: &[f64], t: usize) -> Vec<PhysicsTrigger> {
        assert_eq!(x.len(), self.ema_mean.len());

        self.n_processed += 1;
        let mut point_triggers = Vec::new();

        for i in 0..x.len() {
            let mean = self.ema_mean[i];
            let var = self.ema_var[i];

            // ✅ Минимальный std — 1% от |mean| или 1e-3, что больше
            //    Это защита от "гигантских z" на стабильных датчиках
            let min_std = (mean.abs() * 0.01).max(1e-3);
            let std = var.sqrt().max(min_std);

            let z = (x[i] - mean) / std;

            // ✅ Дебаунсинг: не больше 1 триггера на датчик за last_gap точек
            //    Это убирает серии "одинаковых" триггеров на застывшем значении
            let last_gap = 50; // точек
            let recent = self.triggers.iter().rev()
                .take(20)  // смотрим последние 20 триггеров
                .any(|tr| tr.sensor_idx == i && t.saturating_sub(tr.t) < last_gap);

            if z.abs() > self.z_threshold && self.n_processed > 100 && !recent {
                let trigger = PhysicsTrigger {
                    t,
                    sensor_idx: i,
                    value: x[i],
                    ema_mean: mean,
                    ema_std: std,
                    z_score: z,
                    deviation_pct: 100.0 * (x[i] - mean).abs() / mean.abs().max(1e-6),
                };
                point_triggers.push(trigger.clone());
                self.triggers.push(trigger);
            }

            // Обновляем EMA
            self.ema_mean[i] = self.alpha * x[i] + (1.0 - self.alpha) * self.ema_mean[i];
            let diff = x[i] - self.ema_mean[i];
            self.ema_var[i] = self.alpha * diff * diff + (1.0 - self.alpha) * self.ema_var[i];
        }

        point_triggers
    }


    /// Количество триггеров всего.
    pub fn n_triggers(&self) -> usize {
        self.triggers.len()
    }


    /// Все триггеры.
    pub fn triggers(&self) -> &[PhysicsTrigger] {
        &self.triggers
    }


    /// Триггеры в диапазоне [t_start, t_end).
    pub fn triggers_in_range(&self, t_start: usize, t_end: usize) -> Vec<&PhysicsTrigger> {
        self.triggers
            .iter()
            .filter(|tr| tr.t >= t_start && tr.t < t_end)
            .collect()
    }


    /// Триггеры по датчику.
    pub fn triggers_for_sensor(&self, sensor_idx: usize) -> Vec<&PhysicsTrigger> {
        self.triggers
            .iter()
            .filter(|tr| tr.sensor_idx == sensor_idx)
            .collect()
    }


    /// Статистика по триггерам для каждого датчика.
    pub fn triggers_per_sensor(&self) -> Vec<usize> {
        let n = self.ema_mean.len();
        let mut counts = vec![0usize; n];
        for tr in &self.triggers {
            counts[tr.sensor_idx] += 1;
        }
        counts
    }


    pub fn reset(&mut self) {
        for v in self.ema_mean.iter_mut() {
            *v = 0.0;
        }
        for v in self.ema_var.iter_mut() {
            *v = 1e-6;
        }
        self.triggers.clear();
        self.n_processed = 0;
    }


    pub fn n_sensors(&self) -> usize {
        self.ema_mean.len()
    }

    pub fn z_threshold(&self) -> f64 {
        self.z_threshold
    }

    pub fn alpha(&self) -> f64 {
        self.alpha
    }
}


// ================================================================
// ТЕСТЫ
// ================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create() {
        let fl = FastLayer::new(3, 0.1, 3.0);
        assert_eq!(fl.n_sensors(), 3);
        assert_eq!(fl.n_triggers(), 0);
    }

    #[test]
    fn test_no_triggers_on_stable() {
        let mut fl = FastLayer::new(1, 0.01, 3.0);
        // 1000 точек стабильного сигнала
        for i in 0..1000 {
            fl.update(&[1.0], i);
        }
        // Не должно быть триггеров
        assert_eq!(fl.n_triggers(), 0);
    }

    #[test]
    fn test_trigger_on_jump() {
        let mut fl = FastLayer::new(1, 0.01, 3.0);
        // Набираем статистику
        for i in 0..200 {
            fl.update(&[1.0 + (i as f64 * 0.001).sin() * 0.01], i);
        }
        // Резкий скачок
        fl.update(&[10.0], 200);
        // Должен быть триггер
        assert!(fl.n_triggers() > 0, "триггер не сработал");
    }

    #[test]
    fn test_multiple_sensors() {
        let mut fl = FastLayer::new(3, 0.05, 2.0);
        for i in 0..200 {
            fl.update(&[1.0, 2.0, 3.0], i);
        }
        // Скачок на 2-м датчике
        fl.update(&[1.0, 20.0, 3.0], 200);

        let per_sensor = fl.triggers_per_sensor();
        assert_eq!(per_sensor[1] > 0, true, "триггер должен быть на датчике 1");
    }

    #[test]
    fn test_reset() {
        let mut fl = FastLayer::new(2, 0.1, 2.0);
        for i in 0..200 {
            fl.update(&[1.0, 1.0], i);
        }
        fl.update(&[100.0, 1.0], 200);
        assert!(fl.n_triggers() > 0);

        fl.reset();
        assert_eq!(fl.n_triggers(), 0);
    }

    #[test]
    fn test_triggers_in_range() {
        let mut fl = FastLayer::new(1, 0.01, 2.0);
        for i in 0..200 {
            fl.update(&[1.0], i);
        }
        for i in 200..210 {
            fl.update(&[10.0], i);
        }
        let in_range = fl.triggers_in_range(200, 210);
        assert!(!in_range.is_empty());
    }
}