//! Внутренний решатель ранга над Z_p (общий для batch и PyO3-обёртки).


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

    let mut rows: Vec<Vec<(usize, u64)>> = Vec::with_capacity(n_rows);
    for i in 0..n_rows {
        let start = indptr[i] as usize;
        let end = indptr[i + 1] as usize;
        if start >= end {
            continue;
        }
        let mut row: Vec<(usize, u64)> = Vec::with_capacity(end - start);
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

    if rows.is_empty() {
        return 0;
    }

    rows.sort_unstable_by_key(|r| r.len());

    let mut rank: u64 = 0;
    let mut pivot_cols: std::collections::HashSet<usize> = std::collections::HashSet::new();
    let mut active_start = 0usize;

    while active_start < rows.len() {
        let mut best_idx = active_start;
        let mut min_len = rows[active_start].len();
        for i in (active_start + 1)..rows.len() {
            let l = rows[i].len();
            if l < min_len {
                min_len = l;
                best_idx = i;
                if min_len == 0 {
                    break;
                }
            }
        }

        if min_len == 0 {
            active_start += 1;
            continue;
        }

        rows.swap(active_start, best_idx);
        let pivot_row = std::mem::take(&mut rows[active_start]);

        let mut pivot_c: Option<usize> = None;
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

        let pivot_val = pivot_row
            .iter()
            .find(|&&(c, _)| c == pivot_c)
            .unwrap()
            .1;
        let inv_pivot = mod_pow(pivot_val, p - 2, p);

        let p128 = p as u128;

        for i in (active_start + 1)..rows.len() {
            if rows[i].is_empty() {
                continue;
            }
            let factor = match rows[i].binary_search_by_key(&pivot_c, |&(c, _)| c) {
                Ok(idx) => (rows[i][idx].1 as u128 * inv_pivot as u128 % p128) as u64,
                Err(_) => continue,
            };

            let mut new_row: Vec<(usize, u64)> =
                Vec::with_capacity(rows[i].len() + pivot_row.len());

            let mut it_i = rows[i].iter().peekable();
            let mut it_p = pivot_row.iter().peekable();

            // FIX: используем .copied() и Some((ci, vi)) без &,
            //      чтобы получить значения, а не ссылки.
            while it_i.peek().is_some() || it_p.peek().is_some() {
                match (it_i.peek().copied(), it_p.peek().copied()) {
                    (Some((ci, vi)), Some((cp, vp))) => {
                        if ci < cp {
                            new_row.push((ci, vi));
                            it_i.next();
                        } else if ci > cp {
                            if cp != pivot_c {
                                let nv = (p128
                                    - (factor as u128 * vp as u128) % p128)
                                    % p128;
                                if nv != 0 {
                                    new_row.push((cp, nv as u64));
                                }
                            }
                            it_p.next();
                        } else {
                            if ci != pivot_c {
                                let nv = ((vi as u128 + p128
                                    - (factor as u128 * vp as u128) % p128)
                                    % p128) as u64;
                                if nv != 0 {
                                    new_row.push((ci, nv));
                                }
                            }
                            it_i.next();
                            it_p.next();
                        }
                    }
                    (Some((ci, vi)), None) => {
                        new_row.push((ci, vi));
                        it_i.next();
                    }
                    (None, Some((cp, vp))) => {
                        if cp != pivot_c {
                            let nv = (p128
                                - (factor as u128 * vp as u128) % p128)
                                % p128;
                            if nv != 0 {
                                new_row.push((cp, nv as u64));
                            }
                        }
                        it_p.next();
                    }
                    (None, None) => break,
                }
            }
            rows[i] = new_row;
        }
        active_start += 1;
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
}
