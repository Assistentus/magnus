//! Построение матрицы fr-кода (`rr`, `frf`, `rff`, ...) над Z_p.

use super::magnus_algebra::MagnusBasis;


/// Построитель матрицы кода.
pub struct FrCodeBuilder<'a> {
    basis: &'a MagnusBasis,
    p: u64,
}


impl<'a> FrCodeBuilder<'a> {
    pub fn new(basis: &'a MagnusBasis, p: u64) -> Self {
        Self { basis, p }
    }

    /// Построить CSR-матрицу для списка мономов.
    ///
    /// `relations` — исходные слова (индексы букв).
    /// `code_parts` — например `["rr", "frf"]`.
    ///
    /// Возвращает `(indptr, indices, data, n_rows, n_cols)`.
    /// Все `Vec<i64>` готовы для передачи в numpy/PyO3.
    pub fn build_code(
        &self,
        relations: &[Vec<usize>],
        code_parts: &[&str],
    ) -> Result<(Vec<i64>, Vec<i64>, Vec<i64>, usize, usize), String> {
        // 1. Раскрываем relations один раз.
        let r_generators: Vec<Vec<(u64, u64)>> = relations
            .iter()
            .map(|rel| self.basis.expand_word(rel, self.p))
            .filter(|v| !v.is_empty())
            .collect();

        if r_generators.is_empty() {
            return Ok((vec![0], Vec::new(), Vec::new(), 0, self.basis.dim() as usize));
        }

        let k = self.basis.k();
        let max_deg = self.basis.degree();

        // 2. COO-накопители.
        let mut rows: Vec<i64> = Vec::new();
        let mut cols: Vec<i64> = Vec::new();
        let mut data: Vec<i64> = Vec::new();
        let mut current_row: i64 = 0;

        for part in code_parts {
            let mut chars = part.chars();
            let first = chars
                .next()
                .ok_or_else(|| format!("пустой моном в code_parts: {:?}", part))?;

            // Инициализация.
            let mut current_gens: Vec<Vec<(u64, u64)>> = match first {
                'r' => r_generators.clone(),
                'f' => (0..k)
                    .map(|a| {
                        let idx = self.basis.basis_to_idx(&[a]).unwrap();
                        vec![(idx, 1u64)]
                    })
                    .collect(),
                c => return Err(format!("недопустимый символ: {:?}", c)),
            };

            // Последующие символы.
            for c in chars {
                current_gens = match c {
                    'r' => self.multiply_by_r(&current_gens, &r_generators),
                    'f' => self.multiply_by_f(&current_gens),
                    c => return Err(format!("недопустимый символ: {:?}", c)),
                };
                if current_gens.is_empty() {
                    break;
                }
            }

            // Эмитим строки.
            for polynomial in &current_gens {
                for &(idx, coeff) in polynomial {
                    let c = (coeff as u128 % self.p as u128) as u64;
                    if c != 0 {
                        rows.push(current_row);
                        cols.push(idx as i64);
                        data.push(c as i64);
                    }
                }
                current_row += 1;
            }

            let _ = max_deg; // на будущее
        }

        // 3. COO → CSR.
        let (indptr, indices, data_csr) = self.coo_to_csr(
            &rows, &cols, &data, current_row as usize, self.basis.dim() as usize,
        );
        Ok((indptr, indices, data_csr, current_row as usize, self.basis.dim() as usize))
    }

    /// Умножение каждого генератора справа на набор r-генераторов.
    fn multiply_by_r(
        &self,
        gens: &[Vec<(u64, u64)>],
        r_generators: &[Vec<(u64, u64)>],
    ) -> Vec<Vec<(u64, u64)>> {
        let mut out = Vec::with_capacity(gens.len() * r_generators.len());
        for g in gens {
            for r in r_generators {
                if let Some(prod) = self.multiply_polys(g, r) {
                    out.push(prod);
                }
            }
        }
        out
    }

    /// Умножение каждого генератора справа на каждую букву алфавита `f`.
    fn multiply_by_f(&self, gens: &[Vec<(u64, u64)>]) -> Vec<Vec<(u64, u64)>> {
        let k = self.basis.k();
        let mut out = Vec::with_capacity(gens.len() * k);
        for g in gens {
            for a in 0..k {
                let mut new_g: Vec<(u64, u64)> = Vec::with_capacity(g.len());
                for &(idx, coeff) in g {
                    if let Some(new_idx) = self.append_letter(idx, a) {
                        new_g.push((new_idx, coeff));
                    }
                }
                if !new_g.is_empty() {
                    out.push(self.compact(new_g));
                }
            }
        }
        out
    }

    /// Умножение двух многочленов (по индексам мономов).
    fn multiply_polys(
        &self,
        a: &[(u64, u64)],
        b: &[(u64, u64)],
    ) -> Option<Vec<(u64, u64)>> {
        let mut out: Vec<(u64, u64)> = Vec::with_capacity(a.len() * b.len());
        for &(ia, ca) in a {
            for &(ib, cb) in b {
                if let Some(new_idx) = self.concat_indices(ia, ib) {
                    let prod = (ca as u128 * cb as u128 % self.p as u128) as u64;
                    if prod != 0 {
                        out.push((new_idx, prod));
                    }
                }
            }
        }
        if out.is_empty() {
            return None;
        }
        Some(self.compact(out))
    }

    /// Приписать букву `a` справа к моному с индексом `idx`.
    fn append_letter(&self, idx: u64, a: usize) -> Option<u64> {
        let d = self.degree_of(idx)?;
        if d + 1 > self.basis.degree() {
            return None;
        }
        let local = idx.checked_sub(self.basis.offsets[d])?;
        let new_local = local.checked_mul(self.basis.k() as u64)?
                              .checked_add(a as u64)?;
        self.basis.offsets[d + 1].checked_add(new_local)
    }

    /// Конкатенация мономов `ia` и `ib`.
    fn concat_indices(&self, ia: u64, ib: u64) -> Option<u64> {
        let da = self.degree_of(ia)?;
        let db = self.degree_of(ib)?;
        if da + db > self.basis.degree() {
            return None;
        }
        let la = ia.checked_sub(self.basis.offsets[da])?;
        let lb = ib.checked_sub(self.basis.offsets[db])?;
        let pow = (self.basis.k() as u64).checked_pow(db as u32)?;
        let new_local = la.checked_mul(pow)?.checked_add(lb)?;
        self.basis.offsets[da + db].checked_add(new_local)
    }

    /// Определить степень монома по его индексу.
    #[inline]
    fn degree_of(&self, idx: u64) -> Option<usize> {
        if idx >= self.basis.dim() {
            return None;
        }
        // offsets: [0, 0, K, K+K^2, ...]; ищем первую d, где
        // offsets[d] <= idx < offsets[d+1] (или dim для последнего).
        let offsets = &self.basis.offsets;
        let deg = self.basis.degree();

        // partition_point: первый i, где offsets[i] > idx.
        // offsets[0] = offsets[1] = 0, поэтому для idx=0 → i=2.
        let pos = offsets.partition_point(|&o| o <= idx);
        // pos — индекс первого offset > idx.
        // Значит, idx находится в степени pos - 1.
        let d = pos.checked_sub(1)?;
        if d == 0 || d > deg {
            return None;
        }
        Some(d)
    }

    /// Сортировка по (col) и суммирование одинаковых коэффициентов mod p.
    fn compact(&self, mut v: Vec<(u64, u64)>) -> Vec<(u64, u64)> {
        if v.len() <= 1 {
            if v.len() == 1 && v[0].1 == 0 {
                return Vec::new();
            }
            return v;
        }
        v.sort_unstable_by_key(|&(c, _)| c);
        let p128 = self.p as u128;
        let mut out: Vec<(u64, u64)> = Vec::with_capacity(v.len());
        for (c, val) in v {
            let val_mod = (val as u128 % p128) as u64;
            if val_mod == 0 {
                continue;
            }
            if let Some(last) = out.last_mut() {
                if last.0 == c {
                    last.1 = ((last.1 as u128 + val_mod as u128) % p128) as u64;
                    if last.1 == 0 {
                        out.pop();
                    }
                    continue;
                }
            }
            out.push((c, val_mod));
        }
        out
    }

    /// COO → CSR с объединением дубликатов (row, col) по модулю p.
    fn coo_to_csr(
        &self,
        rows: &[i64],
        cols: &[i64],
        data: &[i64],
        n_rows: usize,
        _n_cols: usize,
    ) -> (Vec<i64>, Vec<i64>, Vec<i64>) {
        // Пустая матрица.
        if rows.is_empty() {
            return (vec![0i64; n_rows + 1], Vec::new(), Vec::new());
        }

        // 1. Сортируем индексы по (row, col).
        let mut order: Vec<usize> = (0..rows.len()).collect();
        order.sort_unstable_by_key(|&i| (rows[i], cols[i]));

        let p128 = self.p as u128;

        // 2. Объединяем дубликаты (row, col) — суммируем по модулю p.
        //    Результат: три параллельных вектора:
        //      uniq_rows, uniq_cols, uniq_data
        let mut uniq_rows: Vec<i64> = Vec::with_capacity(rows.len());
        let mut uniq_cols: Vec<i64> = Vec::with_capacity(rows.len());
        let mut uniq_data: Vec<i64> = Vec::with_capacity(rows.len());

        for &i in &order {
            let r = rows[i];
            let c = cols[i];
            let v = (data[i] as u64) % self.p;

            if v == 0 {
                continue;
            }

            // Если последняя запись имеет тот же (row, col) — складываем.
            if let (Some(&last_r), Some(&last_c)) =
                (uniq_rows.last(), uniq_cols.last())
            {
                if last_r == r && last_c == c {
                    let prev = uniq_data.last_mut().unwrap();
                    let summed =
                        ((*prev as u128 + v as u128) % p128) as i64;
                    if summed == 0 {
                        // Обнулилось — убираем запись.
                        uniq_rows.pop();
                        uniq_cols.pop();
                        uniq_data.pop();
                    } else {
                        *prev = summed;
                    }
                    continue;
                }
            }

            uniq_rows.push(r);
            uniq_cols.push(c);
            uniq_data.push(v as i64);
        }

        // 3. Строим indptr из uniq_rows.
        let mut indptr = vec![0i64; n_rows + 1];
        for &r in &uniq_rows {
            indptr[r as usize + 1] += 1;
        }
        for i in 1..=n_rows {
            indptr[i] += indptr[i - 1];
        }

        (indptr, uniq_cols, uniq_data)
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_degree_of() {
        let b = MagnusBasis::new(3, 3);
        // offsets = [0, 0, 3, 12]
        // idx 0..3 → degree 1
        // idx 3..12 → degree 2
        // idx 12..39 → degree 3
        let builder = FrCodeBuilder::new(&b, 1_000_000_007);
        assert_eq!(builder.degree_of(0), Some(1));
        assert_eq!(builder.degree_of(2), Some(1));
        assert_eq!(builder.degree_of(3), Some(2));
        assert_eq!(builder.degree_of(11), Some(2));
        assert_eq!(builder.degree_of(12), Some(3));
        assert_eq!(builder.degree_of(38), Some(3));
        assert_eq!(builder.degree_of(39), None);
    }

    #[test]
    fn test_build_rr_simple() {
        // 2 relations из 2 букв каждая, code = ["rr"].
        let b = MagnusBasis::new(3, 3);
        let builder = FrCodeBuilder::new(&b, 1_000_000_007);
        let relations = vec![vec![0, 1], vec![1, 2]];
        let (indptr, _indices, _data, n_rows, n_cols) =
            builder.build_code(&relations, &["rr"]).unwrap();
        assert_eq!(n_cols, b.dim() as usize);
        assert_eq!(indptr.len(), n_rows + 1);
        // n_rows должно быть 2 × 2 = 4 (каждая relation × каждая relation)
        assert_eq!(n_rows, 4);
    }

    #[test]
    fn test_build_rr_frf() {
        let b = MagnusBasis::new(2, 3);
        let builder = FrCodeBuilder::new(&b, 1_000_000_007);
        let relations = vec![vec![0, 1]];
        let (indptr, indices, data, n_rows, n_cols) =
            builder.build_code(&relations, &["rr", "frf"]).unwrap();
        assert_eq!(n_cols, b.dim() as usize);
        assert_eq!(indptr.len(), n_rows + 1);
        // Проверим, что последний элемент indptr == nnz
        assert_eq!(*indptr.last().unwrap() as usize, indices.len());
        assert_eq!(indices.len(), data.len());
    }

    #[test]
    fn test_empty_relations() {
        let b = MagnusBasis::new(3, 2);
        let builder = FrCodeBuilder::new(&b, 1_000_000_007);
        let (indptr, indices, data, n_rows, _n_cols) =
            builder.build_code(&[], &["rr"]).unwrap();
        assert_eq!(n_rows, 0);
        assert_eq!(indptr, vec![0]);
        assert!(indices.is_empty());
        assert!(data.is_empty());
    }

    #[test]
    fn test_invalid_code_part() {
        let b = MagnusBasis::new(3, 2);
        let builder = FrCodeBuilder::new(&b, 1_000_000_007);
        let relations = vec![vec![0, 1]];
        assert!(builder.build_code(&relations, &["xr"]).is_err());
    }
}
