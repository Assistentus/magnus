#![allow(unused_unsafe, unsafe_op_in_unsafe_fn)] // Подавляем строгие предупреждения макросов PyO3 под Rust 2024

use pyo3::prelude::*;
use numpy::PyReadonlyArray1;

// Быстрое возведение в степень по модулю (для обратного элемента)
fn mod_pow(mut base: u64, mut exp: u64, modulus: u64) -> u64 {
    let mut res = 1;
    base %= modulus;
    while exp > 0 {
        if exp % 2 == 1 {
            res = (res * base) % modulus;
        }
        exp /= 2;
        base = (base * base) % modulus;
    }
    res
}

#[pyfunction]
fn compute_rank_zp_sparse<'py>(
    _py: Python<'py>,
    indptr: PyReadonlyArray1<'py, i64>,
    indices: PyReadonlyArray1<'py, i64>,
    data: PyReadonlyArray1<'py, i64>,
    _n_cols: usize,
    p: u64,
) -> PyResult<usize> {
    let indptr = indptr.as_slice()?;
    let indices = indices.as_slice()?;
    let data = data.as_slice()?;
    let n_rows = indptr.len() - 1;

    let mut rows: Vec<Vec<(usize, u64)>> = Vec::with_capacity(n_rows);
    
    for i in 0..n_rows {
        let start = indptr[i] as usize;
        let end = indptr[i+1] as usize;
        if start < end {
            let mut row = Vec::with_capacity(end - start);
            for j in start..end {
                let val = (data[j] as u64) % p;
                if val != 0 {
                    row.push((indices[j] as usize, val));
                }
            }
            if !row.is_empty() {
                row.sort_unstable_by_key(|&(c, _)| c);
                rows.push(row);
            }
        }
    }

    if rows.is_empty() {
        return Ok(0);
    }

    rows.sort_unstable_by_key(|r| r.len());

    let mut rank = 0;
    let mut pivot_cols = std::collections::HashSet::new();
    let mut active_start = 0;

    while active_start < rows.len() {
        let mut best_idx = active_start;
        let mut min_len = rows[active_start].len();
        
        // ОПТИМИЗАЦИЯ 1 (Мгновенный выбор пивота): 
        // Если у нас уже есть строка длины 1 или 0, искать более короткую нет смысла.
        // Это экономит 150 миллиардов итераций цикла!
        if min_len > 1 {
            for i in (active_start + 1)..rows.len() {
                let l = rows[i].len();
                if l < min_len {
                    min_len = l;
                    best_idx = i;
                    if min_len <= 1 { break; } // Досрочный выход, лучше не найдем
                }
            }
        }

        if min_len == 0 {
            active_start += 1;
            continue;
        }

        rows.swap(active_start, best_idx);
        
        // Забираем строку во владение без копирования данных
        let pivot_row = std::mem::take(&mut rows[active_start]);

        let mut pivot_c = None;
        for &(c, _) in &pivot_row {
            if !pivot_cols.contains(&c) {
                pivot_c = Some(c);
                break;
            }
        }

        let pivot_c = match pivot_c {
            Some(c) => c,
            None => {
                active_start += 1;
                continue;
            }
        };

        pivot_cols.insert(pivot_c);
        rank += 1;

        let pivot_val = pivot_row.iter().find(|&&(c, _)| c == pivot_c).unwrap().1;
        let inv_pivot = mod_pow(pivot_val, p - 2, p);

        for i in (active_start + 1)..rows.len() {
            // ОПТИМИЗАЦИЯ 2: Если строка уже пустая, пропускаем её мгновенно
            if rows[i].is_empty() {
                continue;
            }

            // Быстрая проверка: есть ли пивотный столбец в строке?
            let factor = match rows[i].binary_search_by_key(&pivot_c, |&(c, _)| c) {
                Ok(idx) => (rows[i][idx].1 * inv_pivot) % p,
                Err(_) => continue, // Пивота нет, строку трогать не надо
            };

            let mut new_row = Vec::with_capacity(rows[i].len() + pivot_row.len());
            let mut iter_i = rows[i].iter().peekable();
            let mut iter_p = pivot_row.iter().peekable();

            while iter_i.peek().is_some() || iter_p.peek().is_some() {
                match (iter_i.peek(), iter_p.peek()) {
                    (Some(&&(c_i, v_i)), Some(&&(c_p, v_p))) => {
                        if c_i < c_p {
                            new_row.push((c_i, v_i));
                            iter_i.next();
                        } else if c_i > c_p {
                            if c_p != pivot_c {
                                let new_val = (p - (factor * v_p) % p) % p;
                                if new_val != 0 {
                                    new_row.push((c_p, new_val));
                                }
                            }
                            iter_p.next();
                        } else {
                            if c_i != pivot_c {
                                let new_val = (v_i + p - (factor * v_p) % p) % p;
                                if new_val != 0 {
                                    new_row.push((c_i, new_val));
                                }
                            }
                            iter_i.next();
                            iter_p.next();
                        }
                    }
                    (Some(&&(c_i, v_i)), None) => {
                        new_row.push((c_i, v_i));
                        iter_i.next();
                    }
                    (None, Some(&&(c_p, v_p))) => {
                        if c_p != pivot_c {
                            let new_val = (p - (factor * v_p) % p) % p;
                            if new_val != 0 {
                                new_row.push((c_p, new_val));
                            }
                        }
                        iter_p.next();
                    }
                    (None, None) => break,
                }
            }
            rows[i] = new_row;
        }
        active_start += 1;
        
        if active_start % 100 == 0 {
            _py.check_signals()?; // Поддержка Ctrl+C
            rows.drain(..active_start);
            active_start = 0;
            rows.sort_unstable_by_key(|r| r.len());
        }
    }

    Ok(rank)
}

#[pymodule]
fn fr_rank_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compute_rank_zp_sparse, m)?)?;
    Ok(())
}
