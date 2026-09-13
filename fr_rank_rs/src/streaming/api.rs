// streaming/api.rs
// ===================================================================
// C API для встраивания в прошивки и ПЛК.
//
// Использование из C:
//   void* handle = streaming_create(7, 0.05, 1.5, 2, 3);
//   double x[7] = {...};
//   int rank, n_states;
//   int grew = streaming_push(handle, x, 7, &rank, &n_states);
//   streaming_reset(handle);
//   streaming_destroy(handle);
// ===================================================================

use super::StreamingProcessor;
use std::os::raw::{c_double, c_int};


/// Opaque handle для C API.
pub struct StreamingHandle {
    processor: StreamingProcessor,
}


/// Создать процессор.
///
/// # Аргументы
/// - `n_sensors`: число датчиков
/// - `alpha`: EMA коэффициент
/// - `n_sigma`: порог в сигмах
/// - `min_count`: минимум повторов
/// - `degree`: степень Magnus
///
/// # Возврат
/// Указатель на handle или NULL при ошибке.
#[no_mangle]
pub extern "C" fn streaming_create(
    n_sensors: c_int,
    alpha: c_double,
    n_sigma: c_double,
    min_count: c_int,
    degree: c_int,
) -> *mut StreamingHandle {
    if n_sensors <= 0 || degree < 1 || min_count < 1 {
        return std::ptr::null_mut();
    }

    let p: u64 = 1_000_000_007;

    let processor = StreamingProcessor::new(
        n_sensors as usize,
        alpha,
        n_sigma,
        min_count as usize,
        p,
        degree as usize,
    );

    Box::into_raw(Box::new(StreamingHandle { processor }))
}


/// Обработать одну точку.
///
/// # Возврат
/// - 1 — ранг вырос
/// - 0 — ранг не изменился
/// - -1 — ошибка
#[no_mangle]
pub extern "C" fn streaming_push(
    handle: *mut StreamingHandle,
    values: *const c_double,
    n: c_int,
    out_rank: *mut c_int,
    out_n_states: *mut c_int,
    out_n_transitions: *mut c_int,
) -> c_int {
    if handle.is_null() || values.is_null() {
        return -1;
    }

    let handle = unsafe { &mut *handle };
    let values_slice = unsafe { std::slice::from_raw_parts(values, n as usize) };

    if values_slice.len() != handle.processor.metrics().t.max(0) as usize
        && values_slice.len() == 0
    {
        return -1;
    }

    let result = handle.processor.process(values_slice);

    unsafe {
        if !out_rank.is_null() {
            *out_rank = result.rank as c_int;
        }
        if !out_n_states.is_null() {
            *out_n_states = result.n_states as c_int;
        }
        if !out_n_transitions.is_null() {
            *out_n_transitions = result.n_transitions as c_int;
        }
    }

    result.rank_increased as c_int
}


/// Обработать пакет точек.
///
/// # Аргументы
/// - `values`: массив размером `n_points * n_sensors`
/// - `n_points`: число точек
/// - `n_sensors`: число датчиков
///
/// # Возврат
/// Число обработанных точек или -1 при ошибке.
#[no_mangle]
pub extern "C" fn streaming_push_batch(
    handle: *mut StreamingHandle,
    values: *const c_double,
    n_points: c_int,
    n_sensors: c_int,
) -> c_int {
    if handle.is_null() || values.is_null() {
        return -1;
    }

    let handle = unsafe { &mut *handle };
    let total = (n_points * n_sensors) as usize;
    let values_slice = unsafe { std::slice::from_raw_parts(values, total) };

    let results = handle.processor.process_batch(values_slice, n_sensors as usize);

    results.len() as c_int
}


/// Получить текущий ранг.
#[no_mangle]
pub extern "C" fn streaming_get_rank(handle: *mut StreamingHandle) -> c_int {
    if handle.is_null() {
        return -1;
    }
    let handle = unsafe { &*handle };
    handle.processor.rank() as c_int
}


/// Получить число состояний.
#[no_mangle]
pub extern "C" fn streaming_get_n_states(handle: *mut StreamingHandle) -> c_int {
    if handle.is_null() {
        return -1;
    }
    let handle = unsafe { &*handle };
    handle.processor.n_states() as c_int
}


/// Получить число переходов.
#[no_mangle]
pub extern "C" fn streaming_get_n_transitions(handle: *mut StreamingHandle) -> c_int {
    if handle.is_null() {
        return -1;
    }
    let handle = unsafe { &*handle };
    handle.processor.n_transitions() as c_int
}


/// Сбросить состояние.
///
/// ВНИМАНИЕ: только при новом запуске установки!
#[no_mangle]
pub extern "C" fn streaming_reset(handle: *mut StreamingHandle) {
    if handle.is_null() {
        return;
    }
    let handle = unsafe { &mut *handle };
    handle.processor.reset();
}


/// Уничтожить handle.
#[no_mangle]
pub extern "C" fn streaming_destroy(handle: *mut StreamingHandle) {
    if handle.is_null() {
        return;
    }
    unsafe {
        drop(Box::from_raw(handle));
    }
}


/// Версия библиотеки.
#[no_mangle]
pub extern "C" fn streaming_version() -> *const u8 {
    b"0.2.0\0".as_ptr()
}