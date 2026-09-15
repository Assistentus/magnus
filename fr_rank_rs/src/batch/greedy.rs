//! Жадный отбор базиса (greedy forward selection) по приросту ранга.

use super::fr_code::FrCodeBuilder;
use super::magnus_algebra::MagnusBasis;
use crate::rank::compute_rank_csr;


/// Оценить абсолютный ранг для набора relations при данном K.
fn compute_rank_for(
    relations: &[Vec<usize>],
    k: usize,
    degree: usize,
    code_parts: &[&str],
    p: u64,
) -> u64 {
    if relations.is_empty() || k == 0 {
        return 0;
    }
    let basis = MagnusBasis::new(k, degree);
    let builder = FrCodeBuilder::new(&basis, p);
    let (indptr, indices, data, n_rows, n_cols) =
        match builder.build_code(relations, code_parts) {
            Ok(t) => t,
            Err(_) => return 0,
        };
    if n_rows == 0 {
        return 0;
    }
    compute_rank_csr(&indptr, &indices, &data, n_rows, n_cols, p)
}


/// Жадный отбор базиса.
///
/// `candidates[i]` — relations, релевантные i-му кандидату.
/// `target_k` — желаемое число выбранных.
/// `initial_selected` — сколько первых взять автоматически.
///
/// Возвращает индексы выбранных кандидатов (в порядке выбора).
pub fn select_generators(
    candidates: &[Vec<Vec<usize>>],
    target_k: usize,
    degree: usize,
    code_parts: &[&str],
    p: u64,
    initial_selected: usize,
) -> Vec<usize> {
    let n = candidates.len();
    let init = initial_selected.min(target_k).min(n);

    let mut selected: Vec<usize> = (0..init).collect();
    let mut remaining: Vec<usize> = (init..n).collect();
    let mut current_relations: Vec<Vec<usize>> = Vec::new();
    for &i in &selected {
        current_relations.extend(candidates[i].iter().cloned());
    }

    while selected.len() < target_k && !remaining.is_empty() {
        let base_rank = compute_rank_for(
            &current_relations,
            selected.len(),
            degree,
            code_parts,
            p,
        );

        let mut best: Option<(usize, i64)> = None;
        for &cand in &remaining {
            // Формируем пробный набор.
            let mut test_rel = current_relations.clone();
            test_rel.extend(candidates[cand].iter().cloned());

            let rank_with = compute_rank_for(
                &test_rel,
                selected.len() + 1,
                degree,
                code_parts,
                p,
            );
            let delta = rank_with as i64 - base_rank as i64;

            if best.map_or(true, |(_, d)| delta > d) {
                best = Some((cand, delta));
            }
        }

        let (best_cand, best_delta) = match best {
            Some(b) if b.1 > 0 => b,
            _ => break,
        };

        selected.push(best_cand);
        remaining.retain(|&x| x != best_cand);
        current_relations.extend(candidates[best_cand].iter().cloned());
    }

    selected
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_candidates() {
        let result = select_generators(&[], 5, 3, &["rr"], 1_000_000_007, 0);
        assert!(result.is_empty());
    }

    #[test]
    fn test_initial_only() {
        let candidates = vec![
            vec![vec![0, 1]],
            vec![vec![1, 2]],
        ];
        let result = select_generators(
            &candidates, 2, 3, &["rr"], 1_000_000_007, 2,
        );
        assert_eq!(result, vec![0, 1]);
    }

    #[test]
    fn test_selects_at_least_one() {
        let candidates: Vec<Vec<Vec<usize>>> = (0..5)
            .map(|i| vec![vec![i % 3, (i + 1) % 3]])
            .collect();
        let result = select_generators(
            &candidates, 3, 3, &["rr"], 1_000_000_007, 0,
        );
        // Должен выбрать хотя бы 1 (обычно больше)
        assert!(!result.is_empty());
        assert!(result.len() <= 3);
    }
}
