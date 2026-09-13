// src/streaming/rank_tracker.rs
// ===================================================================
// Быстрый инкрементальный трекер ранга над Z_p.
//
// Оптимизации:
// - Обход столбцов СТРОКИ (не пивотов) — O(nnz_row) вместо O(rank)
// - take/put вместо get/clone
// - pivot_cols кэшируется для внешнего использования
// - HashMap для degree >= 3, Vec для degree <= 2
// ===================================================================

use std::collections::HashMap;


const DEGREE_VEC_THRESHOLD: usize = 2;


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


#[inline]
fn mod_inverse(a: u64, p: u64) -> u64 {
    mod_pow(a, p - 2, p)
}


enum PivotStorage {
    Vector {
        pivots: Vec<Option<Vec<(u64, u64)>>>,
    },
    Map {
        pivots: HashMap<u64, Vec<(u64, u64)>>,
    },
}


pub struct RankTracker {
    storage: PivotStorage,
    pivot_cols: Vec<u64>,
    buffer: Vec<(u64, u64)>,
    tmp: Vec<(u64, u64)>,
    rank: usize,
    p: u64,
    n_rows_added: usize,
}


impl RankTracker {
    pub fn new(p: u64) -> Self {
        Self::with_degree_hint(p, 3)
    }


    pub fn with_degree_hint(p: u64, degree: usize) -> Self {
        let storage = if degree <= DEGREE_VEC_THRESHOLD {
            PivotStorage::Vector {
                pivots: vec![None; 4096],
            }
        } else {
            PivotStorage::Map {
                pivots: HashMap::with_capacity(4096),
            }
        };

        Self {
            storage,
            pivot_cols: Vec::with_capacity(4096),
            buffer: Vec::with_capacity(64),
            tmp: Vec::with_capacity(64),
            rank: 0,
            p,
            n_rows_added: 0,
        }
    }


    #[inline]
    fn ensure_capacity(&mut self, col: u64) {
        if let PivotStorage::Vector { pivots } = &mut self.storage {
            let needed = col as usize;
            if needed >= pivots.len() {
                let new_size = (needed + 1).next_power_of_two();
                pivots.resize(new_size, None);
            }
        }
    }


    // ✅ ЭТОТ МЕТОД НУЖНО БЫЛО ДОБАВИТЬ
    #[inline]
    fn pivot_exists(&self, col: u64) -> bool {
        match &self.storage {
            PivotStorage::Vector { pivots } => {
                (col as usize) < pivots.len()
                    && pivots[col as usize].is_some()
            }
            PivotStorage::Map { pivots } => pivots.contains_key(&col),
        }
    }


    #[inline]
    fn take_pivot(&mut self, col: u64) -> Option<Vec<(u64, u64)>> {
        match &mut self.storage {
            PivotStorage::Vector { pivots } => {
                if (col as usize) < pivots.len() {
                    pivots[col as usize].take()
                } else {
                    None
                }
            }
            PivotStorage::Map { pivots } => pivots.remove(&col),
        }
    }


    #[inline]
    fn put_pivot(&mut self, col: u64, row: Vec<(u64, u64)>) {
        match &mut self.storage {
            PivotStorage::Vector { pivots } => {
                pivots[col as usize] = Some(row);
            }
            PivotStorage::Map { pivots } => {
                pivots.insert(col, row);
            }
        }
    }


    #[inline]
    fn add_pivot_col(&mut self, col: u64) {
        let pos = self.pivot_cols.binary_search(&col).unwrap_or_else(|e| e);
        self.pivot_cols.insert(pos, col);
    }


    pub fn add_row(&mut self, row: Vec<(u64, u64)>) -> bool {
        if row.is_empty() {
            return false;
        }

        // ============================================================
        // ШАГ 1: Нормализация
        // ============================================================
        self.tmp.clear();
        let mut sorted = row;
        sorted.sort_unstable_by_key(|&(c, _)| c);

        for (c, v) in sorted {
            let v_mod = v % self.p;
            if v_mod == 0 {
                continue;
            }
            if let Some(last) = self.tmp.last_mut() {
                if last.0 == c {
                    last.1 = ((last.1 as u128 + v_mod as u128)
                              % self.p as u128) as u64;
                    if last.1 == 0 {
                        self.tmp.pop();
                    }
                    continue;
                }
            }
            self.tmp.push((c, v_mod));
        }

        if self.tmp.is_empty() {
            return false;
        }

        self.n_rows_added += 1;

        // ============================================================
        // ШАГ 2: Приведение через ОБХОД СТОЛБЦОВ СТРОКИ
        // ============================================================
        std::mem::swap(&mut self.buffer, &mut self.tmp);

        let mut i = 0;
        let mut iterations = 0;
        let max_iterations = self.buffer.len() * self.buffer.len() + 1000;

        while i < self.buffer.len() && iterations < max_iterations {
            iterations += 1;

            let col = self.buffer[i].0;

            if self.pivot_exists(col) {
                let factor = self.buffer[i].1;

                if let Some(pr) = self.take_pivot(col) {
                    self.tmp.clear();
                    self.subtract_into(&pr, factor, col);
                    std::mem::swap(&mut self.buffer, &mut self.tmp);

                    self.put_pivot(col, pr);
                    i = 0;
                } else {
                    i += 1;
                }
            } else {
                i += 1;
            }
        }

        if self.buffer.is_empty() {
            return false;
        }

        // ============================================================
        // ШАГ 3: Новый пивот
        // ============================================================
        let pivot_col = self.buffer[0].0;
        self.ensure_capacity(pivot_col);

        let inv = mod_inverse(self.buffer[0].1, self.p);
        for (_, v) in self.buffer.iter_mut() {
            *v = ((*v as u128 * inv as u128) % self.p as u128) as u64;
        }

        let pivot_row = std::mem::take(&mut self.buffer);
        self.put_pivot(pivot_col, pivot_row);
        self.add_pivot_col(pivot_col);

        self.rank += 1;
        true
    }


    #[inline]
    fn subtract_into(&mut self, pivot_row: &[(u64, u64)],
                      factor: u64, pivot_col: u64) {
        let row = &self.buffer;
        let p128 = self.p as u128;

        let mut i = 0;
        let mut j = 0;

        while i < row.len() || j < pivot_row.len() {
            let (c, v) = if i >= row.len() {
                let (pc, pv) = pivot_row[j];
                j += 1;
                if pc == pivot_col { continue; }
                let new_v = ((p128 - (factor as u128 * pv as u128) % p128)
                             % p128) as u64;
                if new_v == 0 { continue; }
                (pc, new_v)
            } else if j >= pivot_row.len() {
                let (rc, rv) = row[i];
                i += 1;
                if rc == pivot_col { continue; }
                (rc, rv)
            } else {
                let (rc, rv) = row[i];
                let (pc, pv) = pivot_row[j];

                if rc < pc {
                    i += 1;
                    if rc == pivot_col { continue; }
                    (rc, rv)
                } else if rc > pc {
                    j += 1;
                    if pc == pivot_col { continue; }
                    let new_v = ((p128 - (factor as u128 * pv as u128) % p128)
                                 % p128) as u64;
                    if new_v == 0 { continue; }
                    (pc, new_v)
                } else {
                    i += 1;
                    j += 1;
                    if rc == pivot_col { continue; }
                    let new_v = ((rv as u128 + p128
                                  - (factor as u128 * pv as u128) % p128)
                                 % p128) as u64;
                    if new_v == 0 { continue; }
                    (rc, new_v)
                }
            };
            self.tmp.push((c, v));
        }
    }


    #[inline]
    pub fn rank(&self) -> usize {
        self.rank
    }


    #[inline]
    pub fn n_rows_added(&self) -> usize {
        self.n_rows_added
    }


    pub fn pivot_cols(&self) -> &[u64] {
        &self.pivot_cols
    }


    pub fn reset(&mut self) {
        match &mut self.storage {
            PivotStorage::Vector { pivots } => {
                for p in pivots.iter_mut() { *p = None; }
            }
            PivotStorage::Map { pivots } => { pivots.clear(); }
        }
        self.pivot_cols.clear();
        self.buffer.clear();
        self.tmp.clear();
        self.rank = 0;
        self.n_rows_added = 0;
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty() {
        let rt = RankTracker::new(1_000_000_007);
        assert_eq!(rt.rank(), 0);
    }

    #[test]
    fn test_single_row() {
        let mut rt = RankTracker::new(1_000_000_007);
        assert!(rt.add_row(vec![(0, 1), (1, 1)]));
        assert_eq!(rt.rank(), 1);
    }

    #[test]
    fn test_duplicate_row() {
        let mut rt = RankTracker::new(1_000_000_007);
        rt.add_row(vec![(0, 1), (1, 1)]);
        assert!(!rt.add_row(vec![(0, 2), (1, 2)]));
        assert_eq!(rt.rank(), 1);
    }

    #[test]
    fn test_independent_rows() {
        let mut rt = RankTracker::new(1_000_000_007);
        rt.add_row(vec![(0, 1), (1, 1)]);
        rt.add_row(vec![(1, 1), (2, 1)]);
        rt.add_row(vec![(0, 1), (2, 1)]);
        assert_eq!(rt.rank(), 3);
    }

    #[test]
    fn test_pivot_cols() {
        let mut rt = RankTracker::new(1_000_000_007);
        rt.add_row(vec![(0, 1), (1, 1)]);
        rt.add_row(vec![(5, 1), (10, 1)]);
        let cols = rt.pivot_cols();
        assert!(!cols.is_empty());
    }

    #[test]
    fn test_map_storage() {
        let mut rt = RankTracker::with_degree_hint(1_000_000_007, 4);
        for i in 0..100 {
            rt.add_row(vec![
                (i as u64, 1),
                ((i + 1) as u64, 1),
                ((i + 2) as u64, 1),
            ]);
        }
        assert!(rt.rank() > 0);
    }

    #[test]
    fn test_reset() {
        let mut rt = RankTracker::new(1_000_000_007);
        rt.add_row(vec![(0, 1)]);
        rt.add_row(vec![(1, 1)]);
        assert!(rt.rank() > 0);
        rt.reset();
        assert_eq!(rt.rank(), 0);
    }
}