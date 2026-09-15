//! Внутренний решатель ранга над Z_p.

use std::collections::HashMap;


#[inline]
fn mod_pow(mut base: u64, mut exp: u64, modulus: u64) -> u64 {
    let mut res: u64 = 1;
    base %= modulus;
    while exp > 0 {
        if exp % 2 == 1 {
            res = ((res as u128 * base as u128) % modulus as u128) as u64;
        }
        exp /= 2;
        base = ((base as u128 * base as u128) % modulus as u128) as u64;
    }
    res
}


/// Точный ранг разреженной матрицы над Z_p.
///
/// Простой Гаусс с ведущими столбцами, без переупорядочивания строк.
/// Медленнее классического, но устойчив к большим матрицам.
pub fn compute_rank_csr(
    indptr: &[i64],
    indices: &[i64],
    data: &[i64],
    _n_rows: usize,
    _n_cols: usize,
    p: u64,
) -> u64 {
    if indptr.len() < 2 {
        return 0;
    }
    let n_rows = indptr.len() - 1;

    // Читаем строки как Vec<(col, val)>, отсортированные по col.
    let mut rows: Vec<Vec<(usize, u64)>> = Vec::with_capacity(n_rows);
    for i in 0..n_rows {
        let start = indptr[i] as usize;
        let end = indptr[i + 1] as usize;
        if start >= end {
            continue;
        }
        let mut row: Vec<(usize, u64)> = Vec::with_capacity(end - start);
        for j in start..end {
            let c = indices[j] as usize;
            let v = (data[j] as u64) % p;
            if v != 0 {
                row.push((c, v));
            }
        }
        if !row.is_empty() {
            row.sort_unstable_by_key(|&(c, _)| c);
            // Схлопываем дубликаты (на всякий случай).
            let mut compacted: Vec<(usize, u64)> = Vec::with_capacity(row.len());
            for (c, v) in row {
                if let Some(last) = compacted.last_mut() {
                    if last.0 == c {
                        last.1 = ((last.1 as u128 + v as u128) % p as u128) as u64;
                        if last.1 == 0 {
                            compacted.pop();
                        }
                        continue;
                    }
                }
                compacted.push((c, v));
            }
            if !compacted.is_empty() {
                rows.push(compacted);
            }
        }
    }

    if rows.is_empty() {
        return 0;
    }

    // Пивоты: col -> нормализованная строка (Vec<(col, val)>).
    let mut pivot_map: HashMap<usize, Vec<(usize, u64)>> = HashMap::new();
    let mut rank: u64 = 0;
    let p128 = p as u128;

    for row in rows {
        let mut current = row;

        loop {
            if current.is_empty() {
                break;
            }

            // Ведущий столбец — минимальный в текущей строке.
            let (pivot_c, pivot_v) = current[0];

            if let Some(pr) = pivot_map.get(&pivot_c) {
                // Исключаем pivot_c, вычитая factor * pr.
                let pr_pivot_v = pr.iter().find(|&&(c, _)| c == pivot_c).unwrap().1;
                let inv = mod_pow(pr_pivot_v, p - 2, p);
                let factor = (pivot_v as u128 * inv as u128 % p128) as u64;

                let mut new_row: Vec<(usize, u64)> =
                    Vec::with_capacity(current.len() + pr.len());
                let mut i = 0;
                let mut j = 0;
                while i < current.len() || j < pr.len() {
                    let (c, v) = if i >= current.len() {
                        let (pc, pv) = pr[j];
                        j += 1;
                        if pc == pivot_c {
                            continue;
                        }
                        let sub = (factor as u128 * pv as u128 % p128) as u64;
                        let nv = ((p128 - sub as u128) % p128) as u64;
                        if nv == 0 {
                            continue;
                        }
                        (pc, nv)
                    } else if j >= pr.len() {
                        let (cc, cv) = current[i];
                        i += 1;
                        if cc == pivot_c {
                            continue;
                        }
                        (cc, cv)
                    } else {
                        let (cc, cv) = current[i];
                        let (pc, pv) = pr[j];
                        if cc < pc {
                            i += 1;
                            if cc == pivot_c {
                                continue;
                            }
                            (cc, cv)
                        } else if cc > pc {
                            j += 1;
                            if pc == pivot_c {
                                continue;
                            }
                            let sub = (factor as u128 * pv as u128 % p128) as u64;
                            let nv = ((p128 - sub as u128) % p128) as u64;
                            if nv == 0 {
                                continue;
                            }
                            (pc, nv)
                        } else {
                            i += 1;
                            j += 1;
                            if cc == pivot_c {
                                continue;
                            }
                            let sub = (factor as u128 * pv as u128 % p128) as u64;
                            let nv = ((cv as u128 + p128 - sub as u128) % p128) as u64;
                            if nv == 0 {
                                continue;
                            }
                            (cc, nv)
                        }
                    };
                    new_row.push((c, v));
                }
                current = new_row;
            } else {
                // Новый пивот.
                let inv = mod_pow(pivot_v, p - 2, p);
                let normalized: Vec<(usize, u64)> = current
                    .iter()
                    .map(|&(c, v)| (c, (v as u128 * inv as u128 % p128) as u64))
                    .collect();
                pivot_map.insert(pivot_c, normalized);
                rank += 1;
                break;
            }
        }
    }

    rank
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty() {
        assert_eq!(compute_rank_csr(&[0], &[], &[], 0, 0, 1_000_000_007), 0);
    }

    #[test]
    fn test_identity_3() {
        let indptr = vec![0i64, 1, 2, 3];
        let indices = vec![0i64, 1, 2];
        let data = vec![1i64, 1, 1];
        assert_eq!(
            compute_rank_csr(&indptr, &indices, &data, 3, 3, 1_000_000_007),
            3
        );
    }

    #[test]
    fn test_duplicate_rows() {
        let indptr = vec![0i64, 2, 4];
        let indices = vec![0i64, 1, 0, 1];
        let data = vec![1i64, 1, 1, 1];
        assert_eq!(
            compute_rank_csr(&indptr, &indices, &data, 2, 2, 1_000_000_007),
            1
        );
    }

    #[test]
    fn test_zero_row() {
        let indptr = vec![0i64, 0, 1];
        let indices = vec![0i64];
        let data = vec![1i64];
        assert_eq!(
            compute_rank_csr(&indptr, &indices, &data, 2, 2, 1_000_000_007),
            1
        );
    }

    #[test]
    fn test_two_independent_rows() {
        let indptr = vec![0i64, 2, 4];
        let indices = vec![0i64, 1, 0, 1];
        let data = vec![1i64, 1, 1, 2];
        assert_eq!(
            compute_rank_csr(&indptr, &indices, &data, 2, 2, 1_000_000_007),
            2
        );
    }

    #[test]
    fn test_c1_superset_of_c2() {
        // c2: 3 независимые строки.
        let indptr_c2 = vec![0i64, 2, 4, 6];
        let indices_c2 = vec![0i64, 1, 1, 2, 2, 3];
        let data_c2 = vec![1i64, 1, 1, 1, 1, 1];

        // c1: те же 3 строки + 3 новые независимые.
        let indptr_c1 = vec![0i64, 2, 4, 6, 8, 10, 12];
        let indices_c1 = vec![0i64, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6];
        let data_c1 = vec![1i64, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1];

        let rank_c2 = compute_rank_csr(&indptr_c2, &indices_c2, &data_c2, 3, 7, 1_000_000_007);
        let rank_c1 = compute_rank_csr(&indptr_c1, &indices_c1, &data_c1, 6, 7, 1_000_000_007);

        assert_eq!(rank_c2, 3);
        assert_eq!(rank_c1, 6);
        assert!(rank_c1 >= rank_c2, "rank(c1)={} < rank(c2)={}", rank_c1, rank_c2);
    }
}
