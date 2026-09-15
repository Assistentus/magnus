#![allow(unused_unsafe, unsafe_op_in_unsafe_fn)]

use pyo3::prelude::*;
use pyo3::types::PyDict;
use numpy::{PyArray1, PyReadonlyArray1};

pub mod batch;
pub mod rank;
pub mod streaming;

use streaming::StreamingProcessor;


// ================================================================
// Ранг разреженной матрицы над Z_p (тонкая обёртка над rank.rs)
// ================================================================

#[pyfunction]
fn compute_rank_zp_sparse<'py>(
    _py: Python<'py>,
    indptr: PyReadonlyArray1<'py, i64>,
    indices: PyReadonlyArray1<'py, i64>,
    data: PyReadonlyArray1<'py, i64>,
    n_cols: usize,
    p: u64,
) -> PyResult<usize> {
    let indptr_s = indptr.as_slice()?;
    let indices_s = indices.as_slice()?;
    let data_s = data.as_slice()?;

    let n_rows = if indptr_s.is_empty() {
        0
    } else {
        indptr_s.len() - 1
    };

    Ok(rank::compute_rank_csr(
        indptr_s, indices_s, data_s, n_rows, n_cols, p,
    ) as usize)
}


// ================================================================
// Batch: Magnus-алгебра и fr-коды
// ================================================================

#[pyfunction]
fn magnus_expand_word(
    word: Vec<usize>,
    k: usize,
    degree: usize,
    p: u64,
) -> Vec<(u64, u64)> {
    let basis = batch::magnus_algebra::MagnusBasis::new(k, degree);
    basis.expand_word(&word, p)
}


#[pyfunction]
fn build_fr_code_csr<'py>(
    py: Python<'py>,
    relations: Vec<Vec<usize>>,
    code_parts: Vec<String>,
    k: usize,
    degree: usize,
    p: u64,
) -> PyResult<(
    Bound<'py, PyArray1<i64>>,
    Bound<'py, PyArray1<i64>>,
    Bound<'py, PyArray1<i64>>,
    usize,
    usize,
)> {
    let basis = batch::magnus_algebra::MagnusBasis::new(k, degree);
    let builder = batch::fr_code::FrCodeBuilder::new(&basis, p);
    let parts: Vec<&str> = code_parts.iter().map(|s| s.as_str()).collect();

    let (indptr, indices, data, n_rows, n_cols) = builder
        .build_code(&relations, &parts)
        .map_err(pyo3::exceptions::PyValueError::new_err)?;

    Ok((
        PyArray1::from_vec_bound(py, indptr),
        PyArray1::from_vec_bound(py, indices),
        PyArray1::from_vec_bound(py, data),
        n_rows,
        n_cols,
    ))
}


#[pyfunction]
#[pyo3(signature = (candidates, target_k, degree, code_parts, p, initial_selected=3))]
fn select_homological_generators(
    candidates: Vec<Vec<Vec<usize>>>,
    target_k: usize,
    degree: usize,
    code_parts: Vec<String>,
    p: u64,
    initial_selected: usize,
) -> Vec<usize> {
    let parts: Vec<&str> = code_parts.iter().map(|s| s.as_str()).collect();
    batch::greedy::select_generators(
        &candidates, target_k, degree, &parts, p, initial_selected,
    )
}


// ================================================================
// StreamingMagnus — с FAST-уровнем
// ================================================================

#[pyclass]
struct StreamingMagnus {
    processor: StreamingProcessor,
    n_sensors: usize,
}


#[pymethods]
impl StreamingMagnus {
    #[new]
    #[pyo3(signature = (
        n_sensors,
        alpha=0.05,
        n_sigma=1.5,
        min_count=2,
        degree=2,
        path_length=0,
        window_size=0,
        overlap=0,
        // FAST-уровень
        enable_fast=false,
        fast_alpha=0.001,
        fast_z_threshold=3.0
    ))]
    fn new(
        n_sensors: usize,
        alpha: f64,
        n_sigma: f64,
        min_count: usize,
        degree: usize,
        path_length: usize,
        window_size: usize,
        overlap: usize,
        enable_fast: bool,
        fast_alpha: f64,
        fast_z_threshold: f64,
    ) -> PyResult<Self> {
        if n_sensors == 0 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "n_sensors должен быть > 0",
            ));
        }
        if alpha <= 0.0 || alpha > 1.0 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "alpha должен быть в (0, 1]",
            ));
        }
        if n_sigma <= 0.0 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "n_sigma должен быть > 0",
            ));
        }
        if min_count < 1 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "min_count должен быть >= 1",
            ));
        }
        if degree < 1 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "degree должен быть >= 1",
            ));
        }
        if window_size > 0 && overlap >= window_size {
            return Err(pyo3::exceptions::PyValueError::new_err(
                format!(
                    "overlap ({}) должен быть < window_size ({})",
                    overlap, window_size
                ),
            ));
        }
        if enable_fast {
            if fast_alpha <= 0.0 || fast_alpha > 1.0 {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "fast_alpha должен быть в (0, 1]",
                ));
            }
            if fast_z_threshold <= 0.0 {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "fast_z_threshold должен быть > 0",
                ));
            }
        }

        let p: u64 = 1_000_000_007;

        Ok(Self {
            processor: StreamingProcessor::new(
                n_sensors, alpha, n_sigma, min_count, p,
                degree, path_length, window_size, overlap,
                enable_fast, fast_alpha, fast_z_threshold,
            ),
            n_sensors,
        })
    }


    fn process<'py>(
        &mut self,
        _py: Python<'py>,
        values: PyReadonlyArray1<'py, f64>,
    ) -> PyResult<PyObject> {
        let values_slice = values.as_slice()?;

        if values_slice.len() != self.n_sensors {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Ожидалось {} значений, получено {}",
                self.n_sensors,
                values_slice.len()
            )));
        }

        let result = self.processor.process(values_slice);

        Python::with_gil(|py| {
            let dict = PyDict::new_bound(py);
            dict.set_item("t", result.t)?;
            dict.set_item("rank", result.rank)?;
            dict.set_item("n_states", result.n_states)?;
            dict.set_item("n_transitions", result.n_transitions)?;
            dict.set_item("n_words", result.n_words)?;
            dict.set_item("rank_increased", result.rank_increased)?;
            dict.set_item("n_new_words", result.n_new_words)?;
            dict.set_item("state_id", result.state_id)?;
            dict.set_item("window_closed", result.window_closed)?;
            dict.set_item("fast_triggers", result.fast_triggers)?;
            Ok(dict.into())
        })
    }


    fn process_batch_fast<'py>(
        &mut self,
        _py: Python<'py>,
        data: PyReadonlyArray1<'py, f64>,
        n_points: usize,
    ) -> PyResult<PyObject> {
        let slice = data.as_slice()?;

        let expected_len = n_points * self.n_sensors;
        if slice.len() != expected_len {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Ожидалось {} значений, получено {}",
                expected_len, slice.len()
            )));
        }

        let last = self.processor.process_batch_no_results(
            slice, self.n_sensors
        );

        Python::with_gil(|py| {
            let dict = PyDict::new_bound(py);
            dict.set_item("t", last.t)?;
            dict.set_item("rank", last.rank)?;
            dict.set_item("n_states", last.n_states)?;
            dict.set_item("n_transitions", last.n_transitions)?;
            dict.set_item("n_words", last.n_words)?;
            dict.set_item("rank_increased", last.rank_increased)?;
            dict.set_item("n_new_words", last.n_new_words)?;
            dict.set_item("state_id", last.state_id)?;
            dict.set_item("window_closed", last.window_closed)?;
            dict.set_item("fast_triggers", last.fast_triggers)?;
            dict.set_item("n_points", n_points)?;
            Ok(dict.into())
        })
    }


    fn process_batch<'py>(
        &mut self,
        _py: Python<'py>,
        data: PyReadonlyArray1<'py, f64>,
        n_points: usize,
    ) -> PyResult<usize> {
        let slice = data.as_slice()?;

        let expected_len = n_points * self.n_sensors;
        if slice.len() != expected_len {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Ожидалось {} значений, получено {}",
                expected_len, slice.len()
            )));
        }

        let results = self.processor.process_batch(slice, self.n_sensors);
        Ok(results.len())
    }


    fn flush(&mut self) -> bool {
        self.processor.flush()
    }


    fn get_rank(&self) -> usize { self.processor.rank() }
    fn get_n_states(&self) -> usize { self.processor.n_states() }
    fn get_n_transitions(&self) -> usize { self.processor.n_transitions() }
    fn get_n_words(&self) -> usize { self.processor.n_words() }
    fn get_t(&self) -> usize { self.processor.get_t() }
    fn get_degree(&self) -> usize { self.processor.get_degree() }
    fn get_path_length(&self) -> usize { self.processor.get_path_length() }
    fn get_p(&self) -> u64 { self.processor.get_p() }

    fn get_window_size(&self) -> usize { self.processor.get_window_size() }
    fn get_overlap(&self) -> usize { self.processor.get_overlap() }
    fn get_n_windows_closed(&self) -> usize { self.processor.n_windows_closed() }
    fn get_path_len(&self) -> usize { self.processor.path_len() }

    fn get_window_fingerprints(&self) -> Vec<(usize, usize, usize, usize, usize, usize, usize, bool, bool)> {
        self.processor
            .window_fingerprints()
            .iter()
            .map(|fp| {
                (
                    fp.t_start, fp.t_end, fp.n_points, fp.rank,
                    fp.n_states, fp.n_words, fp.n_transitions,
                    fp.is_partial, fp.is_tail,
                )
            })
            .collect()
    }

    fn get_current_fingerprint(&self) -> (usize, usize, usize, usize, usize, usize, usize, bool, bool) {
        let fp = self.processor.current_window_fingerprint();
        (
            fp.t_start, fp.t_end, fp.n_points, fp.rank,
            fp.n_states, fp.n_words, fp.n_transitions,
            fp.is_partial, fp.is_tail,
        )
    }


    fn metrics<'py>(&self, _py: Python<'py>) -> PyResult<PyObject> {
        let m = self.processor.metrics();
        Python::with_gil(|py| {
            let dict = PyDict::new_bound(py);
            dict.set_item("t", m.t)?;
            dict.set_item("rank", m.rank)?;
            dict.set_item("n_states", m.n_states)?;
            dict.set_item("n_transitions", m.n_transitions)?;
            dict.set_item("n_words", m.n_words)?;
            dict.set_item("n_rows_added", m.n_rows_added)?;
            dict.set_item("n_windows_closed", m.n_windows_closed)?;
            dict.set_item("fast_n_triggers", m.fast_n_triggers)?;
            Ok(dict.into())
        })
    }

    fn get_relations(&self) -> Vec<(usize, usize)> {
        self.processor.relations()
    }

    fn reset(&mut self) {
        self.processor.reset();
    }

    #[getter]
    fn n_sensors(&self) -> usize {
        self.n_sensors
    }

    // ============================================================
    // FAST-УРОВЕНЬ
    // ============================================================

    /// Все триггеры: (t, sensor_idx, value, z_score, deviation_pct)
    fn get_fast_triggers(&self) -> Vec<(usize, usize, f64, f64, f64)> {
        self.processor.fast_triggers()
    }

    fn get_fast_n_triggers(&self) -> usize {
        self.processor.fast_n_triggers()
    }

    fn get_fast_triggers_per_sensor(&self) -> Vec<usize> {
        self.processor.fast_triggers_per_sensor()
    }

    fn get_fast_enabled(&self) -> bool {
        self.processor.fast_enabled()
    }

    /// Триггеры FAST-уровня в диапазоне [t_start, t_end).
    fn get_fast_triggers_in_range(
        &self,
        t_start: usize,
        t_end: usize,
    ) -> Vec<(usize, usize, f64, f64, f64)> {
        self.processor.fast_triggers_in_range(t_start, t_end)
    }
}


// ================================================================
// РЕГИСТРАЦИЯ МОДУЛЯ
// ================================================================

#[pymodule]
fn fr_rank_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compute_rank_zp_sparse, m)?)?;
    m.add_function(wrap_pyfunction!(magnus_expand_word, m)?)?;
    m.add_function(wrap_pyfunction!(build_fr_code_csr, m)?)?;
    m.add_function(wrap_pyfunction!(select_homological_generators, m)?)?;
    m.add_class::<StreamingMagnus>()?;
    Ok(())
}
