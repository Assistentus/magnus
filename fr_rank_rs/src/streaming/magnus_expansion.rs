// src/streaming/magnus_expansion.rs
// ===================================================================
// Раскрытие Magnus для отношений.
// Поддерживает ЛЮБОЕ degree.
// ===================================================================

pub struct MagnusExpansion {
    degree: usize,
    p: u64,
}


impl MagnusExpansion {
    pub fn new(degree: usize, p: u64) -> Self {
        assert!(degree >= 1);
        Self { degree, p }
    }


    pub fn total_dim(&self, k: usize) -> u64 {
        let mut total: u64 = 0;
        let mut power: u64 = 1;
        for _ in 0..self.degree {
            power = power.saturating_mul(k as u64);
            total = total.saturating_add(power);
        }
        total
    }


    fn offsets(&self, k: usize) -> Vec<u64> {
        let mut offsets = vec![0u64; self.degree + 2];
        let mut total: u64 = 0;
        let mut power: u64 = 1;

        for d in 1..=self.degree {
            power = power.saturating_mul(k as u64);
            offsets[d] = total;
            total = total.saturating_add(power);
        }

        offsets
    }


    /// Построить строку для слова произвольной длины.
    pub fn build_word_row(&self, word: &[usize], k: usize) -> Vec<(u64, u64)> {
        let m = word.len();

        if m == 0 {
            return Vec::new();
        }

        let offsets = self.offsets(k);
        let mut row: Vec<(u64, u64)> = Vec::new();

        for d in 1..=self.degree.min(m) {
            let mut indices = Vec::with_capacity(d);
            self.generate_combinations(
                word, d, 0, &mut indices,
                &offsets, k, &mut row,
            );
        }

        row.sort_unstable_by_key(|&(c, _)| c);

        let mut compacted: Vec<(u64, u64)> = Vec::with_capacity(row.len());
        for (c, v) in row {
            let v_mod = v % self.p;
            if v_mod == 0 { continue; }

            if let Some(last) = compacted.last_mut() {
                if last.0 == c {
                    last.1 = ((last.1 as u128 + v_mod as u128)
                              % self.p as u128) as u64;
                    if last.1 == 0 { compacted.pop(); }
                    continue;
                }
            }
            compacted.push((c, v_mod));
        }

        compacted
    }


    /// build_relation_row для совместимости с transitions-кодом.
    pub fn build_relation_row(&self, a: usize, b: usize, k: usize) -> Vec<(u64, u64)> {
        self.build_word_row(&[a, b], k)
    }


    fn generate_combinations(
        &self,
        word: &[usize],
        d: usize,
        start: usize,
        indices: &mut Vec<usize>,
        offsets: &[u64],
        k: usize,
        row: &mut Vec<(u64, u64)>,
    ) {
        if indices.len() == d {
            let col = self.compute_column(indices, offsets, k);
            row.push((col, 1));
            return;
        }

        let m = word.len();
        let remaining = d - indices.len();

        if m < remaining { return; }

        let max_i = m - remaining;
        for i in start..=max_i {
            indices.push(word[i]);
            self.generate_combinations(
                word, d, i + 1, indices, offsets, k, row,
            );
            indices.pop();
        }
    }


    #[inline]
    fn compute_column(&self, indices: &[usize], offsets: &[u64], k: usize) -> u64 {
        let d = indices.len();
        let mut idx: u64 = 0;

        for &val in indices {
            idx = idx.saturating_mul(k as u64).saturating_add(val as u64);
        }

        offsets[d].saturating_add(idx)
    }


    pub fn degree(&self) -> usize {
        self.degree
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_degree_3_short_word() {
        let mag = MagnusExpansion::new(3, 1_000_000_007);
        let row = mag.build_word_row(&[0, 1], 3);
        // Слово из 2 букв — максимум степень 2
        assert_eq!(row.len(), 3);
    }

    #[test]
    fn test_degree_4_long_word() {
        let mag = MagnusExpansion::new(4, 1_000_000_007);
        let word = vec![0, 1, 2, 3];
        let row = mag.build_word_row(&word, 5);
        // C(4,1) + C(4,2) + C(4,3) + C(4,4) = 4+6+4+1 = 15
        assert_eq!(row.len(), 15);
    }

    #[test]
    fn test_degree_5_long_word() {
        let mag = MagnusExpansion::new(5, 1_000_000_007);
        let word = vec![0, 1, 2, 3, 4];
        let row = mag.build_word_row(&word, 6);
        // C(5,1)+C(5,2)+C(5,3)+C(5,4)+C(5,5) = 5+10+10+5+1 = 31
        assert_eq!(row.len(), 31);
    }
}