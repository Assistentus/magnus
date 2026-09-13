// src/streaming/state_graph.rs
// ===================================================================
// Граф состояний с ПУТЯМИ и подсчётом частоты слов.
//
// Оптимизация: word_counts использует хеш u64 вместо Vec<usize>.
// word_to_vec УБРАН — слово эмитится сразу при достижении min_count.
//
// Добавлено: soft_reset — сохраняет хвост path для overlap.
// ===================================================================

use std::collections::{HashMap, VecDeque};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};


#[inline]
fn hash_word(word: &[usize]) -> u64 {
    let mut hasher = DefaultHasher::new();
    word.hash(&mut hasher);
    hasher.finish()
}


pub struct StateGraph {
    state_to_id: HashMap<Vec<u8>, usize>,
    id_to_state: Vec<Vec<u8>>,

    /// Частота слов: хеш → количество.
    word_counts: HashMap<u64, usize>,

    /// Переходы.
    transitions: HashMap<(usize, usize), usize>,

    /// Путь последних состояний.
    path: VecDeque<usize>,

    path_length: usize,
    min_count: usize,
}


impl StateGraph {
    pub fn new(min_count: usize, path_length: usize) -> Self {
        assert!(min_count >= 1, "min_count >= 1");
        assert!(path_length >= 2, "path_length >= 2");

        Self {
            state_to_id: HashMap::new(),
            id_to_state: Vec::new(),
            word_counts: HashMap::new(),
            transitions: HashMap::new(),
            path: VecDeque::with_capacity(path_length),
            path_length,
            min_count,
        }
    }


    pub fn add_state(&mut self, state: Vec<u8>) -> (usize, Vec<Vec<usize>>) {
        let id = match self.state_to_id.get(&state) {
            Some(&existing) => existing,
            None => {
                let new_id = self.id_to_state.len();
                self.state_to_id.insert(state.clone(), new_id);
                self.id_to_state.push(state);
                new_id
            }
        };

        if let Some(&prev) = self.path.back() {
            let pair = (prev, id);
            *self.transitions.entry(pair).or_insert(0) += 1;
        }

        self.path.push_back(id);
        if self.path.len() > self.path_length {
            self.path.pop_front();
        }

        let mut new_words: Vec<Vec<usize>> = Vec::new();

        if self.path.len() >= 2 {
            let path_vec: Vec<usize> = self.path.iter().copied().collect();

            for len in 2..=path_vec.len() {
                let word_slice = &path_vec[path_vec.len() - len..];
                let h = hash_word(word_slice);

                let count = self.word_counts.entry(h).or_insert(0);
                *count += 1;

                if *count == self.min_count {
                    let word: Vec<usize> = word_slice.to_vec();
                    new_words.push(word);
                }
            }
        }

        (id, new_words)
    }


    pub fn n_states(&self) -> usize { self.id_to_state.len() }
    pub fn n_transitions(&self) -> usize { self.transitions.len() }
    pub fn n_words(&self) -> usize { self.word_counts.len() }


    pub fn get_relations(&self) -> Vec<(usize, usize)> {
        self.transitions
            .iter()
            .filter(|(_, c)| **c >= self.min_count)
            .map(|(pair, _)| *pair)
            .collect()
    }

    pub fn get_state(&self, id: usize) -> Option<&Vec<u8>> {
        self.id_to_state.get(id)
    }

    pub fn get_transition_count(&self, from: usize, to: usize) -> usize {
        *self.transitions.get(&(from, to)).unwrap_or(&0)
    }

    pub fn path_length(&self) -> usize { self.path_length }


    /// Полный сброс.
    pub fn reset(&mut self) {
        self.state_to_id.clear();
        self.id_to_state.clear();
        self.word_counts.clear();
        self.transitions.clear();
        self.path.clear();
    }


    /// ✅ soft_reset: сохраняет хвост path длиной keep_path_last.
    ///
    /// Используется при overlap-режиме, когда rank_tracker сбрасывается,
    /// но path (последние состояния) сохраняется для непрерывности.
    ///
    /// state_to_id и id_to_state НЕ очищаются — иначе path потеряет ID.
    pub fn soft_reset(&mut self, keep_path_last: usize) {
        // Сбрасываем счётчики
        self.word_counts.clear();
        self.transitions.clear();

        // Обрезаем path, оставляя только последние keep_path_last элементов
        let keep = keep_path_last.min(self.path.len());
        while self.path.len() > keep {
            self.path.pop_front();
        }
        // path_length остаётся неизменным для новых добавлений
    }


    /// Текущая длина path (для отладки).
    pub fn path_len(&self) -> usize {
        self.path.len()
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create() {
        let sg = StateGraph::new(2, 4);
        assert_eq!(sg.n_states(), 0);
        assert_eq!(sg.n_words(), 0);
    }

    #[test]
    fn test_add_state() {
        let mut sg = StateGraph::new(2, 4);
        let (id1, _) = sg.add_state(vec![0]);
        assert_eq!(id1, 0);
        let (id2, _) = sg.add_state(vec![1]);
        assert_eq!(id2, 1);
        let (id3, _) = sg.add_state(vec![0]);
        assert_eq!(id3, 0);
        assert_eq!(sg.n_states(), 2);
    }

    #[test]
    fn test_soft_reset_keeps_path() {
        let mut sg = StateGraph::new(2, 4);
        sg.add_state(vec![0]);
        sg.add_state(vec![1]);
        sg.add_state(vec![2]);
        sg.add_state(vec![3]);
        sg.add_state(vec![4]);

        assert_eq!(sg.path_len(), 4);

        sg.soft_reset(2);

        assert_eq!(sg.path_len(), 2);
        // state_to_id НЕ очищен
        assert_eq!(sg.n_states(), 5);
        // word_counts ОЧИЩЕН
        assert_eq!(sg.n_words(), 0);
    }

    #[test]
    fn test_soft_reset_does_not_break_path() {
        let mut sg = StateGraph::new(2, 4);
        sg.add_state(vec![0]);
        sg.add_state(vec![1]);
        sg.add_state(vec![2]);
        sg.add_state(vec![3]);

        sg.soft_reset(2);

        // После soft_reset добавление нового состояния должно работать
        let (id, _words) = sg.add_state(vec![4]);
        // state_to_id сохранил 0,1,2,3 → новый ID = 4
        assert_eq!(id, 4);
    }

    #[test]
    fn test_reset_full() {
        let mut sg = StateGraph::new(2, 3);
        sg.add_state(vec![0]);
        sg.add_state(vec![1]);
        sg.reset();
        assert_eq!(sg.n_states(), 0);
        assert_eq!(sg.n_words(), 0);
        assert_eq!(sg.path_len(), 0);
    }
}