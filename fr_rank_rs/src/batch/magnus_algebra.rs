//! Магнус-алгебра для batch-режима (не потоковая).
//!
//! Аналог Python-класса `MagnusAlgebra`:
//! - базис по индексам (K-ичная система счисления),
//! - `expand_word` — раскрытие слова в разреженный вектор над Z_p.

use std::collections::HashMap;


/// Магнус-базис фиксированной степени.
///
/// Все мономы степени `d ∈ [1, degree]` над алфавитом из `K` букв.
/// Индекс монома `(a_1, ..., a_d)` вычисляется как
/// `offsets[d] + a_1 * K^{d-1} + ... + a_d`.
#[derive(Debug, Clone)]
pub struct MagnusBasis {
    k: usize,
    degree: usize,
    /// `offsets[d]` — начало диапазона индексов степени `d`.
    /// Длина `degree + 1`, `offsets[0] = 0`.
    /// `pub(crate)` — нужно для `fr_code.rs`.
    pub(crate) offsets: Vec<u64>,
    /// Полная размерность: сумма `K^d` по `d=1..=degree`.
    dim: u64,
}


impl MagnusBasis {
    pub fn new(k: usize, degree: usize) -> Self {
        assert!(k > 0, "K должен быть > 0");
        assert!(degree >= 1, "degree должен быть >= 1");

        let mut offsets = vec![0u64; degree + 1];
        let mut total: u64 = 0;
        let mut power: u64 = 1;

        for d in 1..=degree {
            power = power
                .checked_mul(k as u64)
                .expect("K^degree переполняет u64");
            offsets[d] = total;
            total = total
                .checked_add(power)
                .expect("dim переполняет u64");
        }

        Self { k, degree, offsets, dim: total }
    }

    #[inline]
    pub fn k(&self) -> usize { self.k }

    #[inline]
    pub fn degree(&self) -> usize { self.degree }

    #[inline]
    pub fn dim(&self) -> u64 { self.dim }

    /// Индекс монома по его базису. `None`, если степень вне `[1, degree]`
    /// или буква вне `[0, K)`.
    pub fn basis_to_idx(&self, basis: &[usize]) -> Option<u64> {
        let d = basis.len();
        if d == 0 || d > self.degree {
            return None;
        }
        let mut idx: u64 = 0;
        for &v in basis {
            if v >= self.k {
                return None;
            }
            idx = idx.checked_mul(self.k as u64)?
                     .checked_add(v as u64)?;
        }
        self.offsets[d].checked_add(idx)
    }

    /// Обратное преобразование. `None`, если индекс вне диапазона.
    pub fn idx_to_basis(&self, idx: u64) -> Option<Vec<usize>> {
        if idx >= self.dim {
            return None;
        }

        // Ищем степень: единственный d, для которого
        // offsets[d] <= idx < offsets[d+1] (или dim для d = degree).
        let mut d: Option<usize> = None;
        for candidate in 1..=self.degree {
            let lo = self.offsets[candidate];
            let hi = if candidate < self.degree {
                self.offsets[candidate + 1]
            } else {
                self.dim
            };
            if idx >= lo && idx < hi {
                d = Some(candidate);
                break;
            }
        }
        let d = d?;

        let mut local = idx - self.offsets[d];
        let mut basis = vec![0usize; d];
        for i in (0..d).rev() {
            basis[i] = (local % self.k as u64) as usize;
            local /= self.k as u64;
        }
        Some(basis)
    }

    /// Раскрытие слова в разреженный вектор над Z_p.
    ///
    /// Возвращает `Vec<(idx, coeff)>`, отсортированный по `idx`,
    /// без нулевых коэффициентов.
    ///
    /// Логика: для каждой подпоследовательности слова длины
    /// `d ∈ [1, min(degree, len)]` берётся моном степени `d`
    /// с коэффициентом 1. Если одинаковые мономы встречаются
    /// несколько раз — коэффициенты складываются mod p.
    ///
    /// ВАЖНО: если слово содержит букву вне `[0, K)`, возвращается
    /// пустой вектор. Это нужно для greedy-отбора, где алфавит
    /// растёт итеративно, и relation может ссылаться на ещё не
    /// выбранные буквы.
    pub fn expand_word(&self, word: &[usize], p: u64) -> Vec<(u64, u64)> {
        if word.is_empty() {
            return Vec::new();
        }
        // Буквы вне [0, K) → пустой вектор (не паникуем).
        if word.iter().any(|&w| w >= self.k) {
            return Vec::new();
        }

        let m = word.len();
        let max_d = self.degree.min(m);

        let mut acc: HashMap<u64, u64> = HashMap::new();
        let mut indices: Vec<usize> = Vec::with_capacity(max_d);

        for d in 1..=max_d {
            indices.clear();
            Self::enumerate_combinations(
                word, d, 0, &mut indices,
                &mut |combo| {
                    if let Some(col) = self.basis_to_idx(combo) {
                        let e = acc.entry(col).or_insert(0u64);
                        *e = e.wrapping_add(1);
                    }
                },
            );
        }

        let p128 = p as u128;
        let mut out: Vec<(u64, u64)> = acc
            .into_iter()
            .map(|(c, v)| (c, (v as u128 % p128) as u64))
            .filter(|&(_, v)| v != 0)
            .collect();
        out.sort_unstable_by_key(|&(c, _)| c);
        out
    }

    /// Рекурсивный обход сочетаний длины `d` из `word`
    /// в порядке возрастания индексов.
    fn enumerate_combinations<F: FnMut(&[usize])>(
        word: &[usize],
        d: usize,
        start: usize,
        indices: &mut Vec<usize>,
        f: &mut F,
    ) {
        if indices.len() == d {
            f(indices);
            return;
        }
        // Защита от underflow: если indices уже длиннее d — выходим.
        if indices.len() > d {
            return;
        }
        let remaining = d - indices.len();
        let m = word.len();
        if m < remaining {
            return;
        }
        let max_i = m - remaining;
        for i in start..=max_i {
            indices.push(word[i]);
            Self::enumerate_combinations(word, d, i + 1, indices, f);
            indices.pop();
        }
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new() {
        let b = MagnusBasis::new(3, 2);
        assert_eq!(b.k(), 3);
        assert_eq!(b.degree(), 2);
        // dim = 3 + 9 = 12
        assert_eq!(b.dim(), 12);
    }

    #[test]
    fn test_basis_to_idx_simple() {
        let b = MagnusBasis::new(3, 3);
        // degree 1: offsets[1] = 0. [0] → 0, [1] → 1, [2] → 2
        assert_eq!(b.basis_to_idx(&[0]).unwrap(), 0);
        assert_eq!(b.basis_to_idx(&[1]).unwrap(), 1);
        assert_eq!(b.basis_to_idx(&[2]).unwrap(), 2);
        // degree 2: offsets[2] = 3. [0,0] → 3, [0,1] → 4, [2,2] → 11
        assert_eq!(b.basis_to_idx(&[0, 0]).unwrap(), 3);
        assert_eq!(b.basis_to_idx(&[0, 1]).unwrap(), 4);
        assert_eq!(b.basis_to_idx(&[2, 2]).unwrap(), 11);
    }

    #[test]
    fn test_basis_to_idx_out_of_range() {
        let b = MagnusBasis::new(3, 2);
        assert!(b.basis_to_idx(&[3]).is_none());       // буква вне K
        assert!(b.basis_to_idx(&[]).is_none());        // пустой
        assert!(b.basis_to_idx(&[0, 0, 0]).is_none()); // степень > degree
    }

    #[test]
    fn test_roundtrip_basis_idx() {
        let b = MagnusBasis::new(3, 3);
        for idx in 0..b.dim() {
            let basis = b.idx_to_basis(idx).unwrap();
            let back = b.basis_to_idx(&basis).unwrap();
            assert_eq!(idx, back, "roundtrip failed for idx={}", idx);
        }
    }

    #[test]
    fn test_expand_word_length_2() {
        // Слово из 2 букв, degree 4.
        // degree 1: [0], [1] → 2 монома
        // degree 2: [0,1] → 1 моном
        let b = MagnusBasis::new(3, 4);
        let row = b.expand_word(&[0, 1], 1_000_000_007);
        assert_eq!(row.len(), 3);
    }

    #[test]
    fn test_expand_word_length_3() {
        // Слово [0,1,2], degree 4.
        // degree 1: [0],[1],[2]
        // degree 2: [0,1],[0,2],[1,2]
        // degree 3: [0,1,2]
        // Итого: 3 + 3 + 1 = 7
        let b = MagnusBasis::new(3, 4);
        let row = b.expand_word(&[0, 1, 2], 1_000_000_007);
        assert_eq!(row.len(), 7);
    }

    #[test]
    fn test_expand_word_degree_2_bound() {
        // degree 2, слово [0,1,0,1]
        // degree 1: [0], [1] → 2
        // degree 2: [0,0], [0,1], [1,0], [1,1] → 4
        // Всего: 6
        let b = MagnusBasis::new(2, 2);
        let row = b.expand_word(&[0, 1, 0, 1], 1_000_000_007);
        assert_eq!(row.len(), 6);
    }

    #[test]
    fn test_expand_word_repeated() {
        // Слово [0,0,0], degree 4.
        // degree 1: [0] с коэф. 3
        // degree 2: [0,0] с коэф. C(3,2)=3
        // degree 3: [0,0,0] с коэф. C(3,3)=1
        // Всего 3 ненулевых записи.
        let b = MagnusBasis::new(3, 4);
        let row = b.expand_word(&[0, 0, 0], 1_000_000_007);
        assert_eq!(row.len(), 3);
        let get = |idx: u64| row.iter().find(|&&(c, _)| c == idx).map(|&(_, v)| v);
        assert_eq!(get(0), Some(3));  // [0]
        assert_eq!(get(3), Some(3));  // [0,0]  — offsets[2]=3
        assert_eq!(get(12), Some(1)); // [0,0,0] — offsets[3]=12
    }

    #[test]
    fn test_expand_word_out_of_alphabet() {
        // Слово содержит букву вне [0, K) — должен вернуться пустой вектор,
        // а не паника. Это критично для greedy-отбора.
        let b = MagnusBasis::new(3, 4);
        let row = b.expand_word(&[0, 5, 1], 1_000_000_007);
        assert!(row.is_empty(), "Ожидался пустой вектор, получено {:?}", row);
    }

    #[test]
    fn test_expand_word_all_out_of_alphabet() {
        let b = MagnusBasis::new(2, 3);
        let row = b.expand_word(&[10, 20, 30], 1_000_000_007);
        assert!(row.is_empty());
    }
}
