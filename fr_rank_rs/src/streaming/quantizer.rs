
// streaming/quantizer.rs
// ===================================================================
// Адаптивное квантование сигналов с датчиков.
//
// Использует EMA (экспоненциальное скользящее среднее) для оценки
// локального шума. НЕТ СКОЛЬЗЯЩЕГО ОКНА — только EMA.
//
// Вход:  x ∈ ℝ^n
// Выход: state ∈ {0,1,2}^n
//   0 = норма (|delta| < threshold)
//   1 = рост   (delta > threshold)
//   2 = падение (delta < -threshold)
// ===================================================================

pub struct AdaptiveQuantizer {
    n_sensors: usize,
    alpha: f64,
    n_sigma: f64,
    prev_value: Option<Vec<f64>>,
    ema_abs_delta: Vec<f64>,
}


impl AdaptiveQuantizer {
    pub fn new(n_sensors: usize, alpha: f64, n_sigma: f64) -> Self {
        assert!(alpha > 0.0 && alpha <= 1.0, "alpha должен быть в (0, 1]");
        assert!(n_sigma > 0.0, "n_sigma должен быть > 0");

        Self {
            n_sensors,
            alpha,
            n_sigma,
            prev_value: None,
            ema_abs_delta: vec![1e-6; n_sensors],
        }
    }


    /// Квантовать точку.
    ///
    /// Возвращает состояние: 0, 1, 2 для каждого датчика.
    pub fn quantize(&mut self, x: &[f64]) -> Vec<u8> {
        assert_eq!(x.len(), self.n_sensors);

        let mut states = vec![0u8; self.n_sensors];

        if let Some(prev) = &self.prev_value {
            for i in 0..self.n_sensors {
                let delta = x[i] - prev[i];
                let abs_delta = delta.abs();

                // Обновляем EMA (не окно!)
                self.ema_abs_delta[i] =
                    self.alpha * abs_delta + (1.0 - self.alpha) * self.ema_abs_delta[i];

                // Адаптивный порог
                let eps = self.n_sigma * self.ema_abs_delta[i] + 1e-9;

                if delta > eps {
                    states[i] = 1; // Рост
                } else if delta < -eps {
                    states[i] = 2; // Падение
                }
                // Иначе 0 (норма)
            }
        }

        self.prev_value = Some(x.to_vec());
        states
    }


    pub fn reset(&mut self) {
        self.prev_value = None;
        self.ema_abs_delta = vec![1e-6; self.n_sensors];
    }


    pub fn n_sensors(&self) -> usize {
        self.n_sensors
    }
}