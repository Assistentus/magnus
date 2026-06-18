
import re
import gc
from collections import Counter
from typing import List, Optional

from .magnus import MagnusAlgebra
from .codes import FRCodeRegistry
from .solver import HomologySolver


class TextPresentation:
    """
    ЧТО СЧИТАЕМ: Копредставление группы G = <V | R>, порожденное текстом.
    МАТЕМАТИКА: 
      - V (образующие) выбираются по их топологической значимости (приросту абсолютного ранга).
      - R (отношения) строятся строго на основе отобранных узлов V.
    ЗАЧЕМ: Чтобы избежать "алгебраической воды" и построить триангуляцию 
           вокруг истинных смысловых хабов, игнорируя частотный шум.
    """
    
    def __init__(self, text: str, k_vocab: int = 30, max_relations: int = 2500, 
                 custom_vocab: Optional[List[str]] = None):
        self.k_vocab = k_vocab
        self.max_relations = max_relations
        
        if custom_vocab is not None:
            self.vocab = custom_vocab[:k_vocab]
        else:
            self.vocab = self._select_homological_generators(text, k_vocab)
            
        self.word_to_idx = {w: i for i, w in enumerate(self.vocab)}
        self.relations = self._build_relations(text)

    def _select_homological_generators(self, text: str, target_k: int) -> List[str]:
        # 1. Получаем пул кандидатов
        words = re.findall(r'[а-яёa-z]+', text.lower())
        
        # КРИТИЧЕСКАЯ ПРАВКА: len(w) >= 2. 
        # Это сохраняет "не", "мы", "он", "я", "но", "да", но отсеивает мусорные предлоги "в", "к", "с", "о".
        valid_words = [w for w in words if len(w) >= 2]
        candidates = [w for w, _ in Counter(valid_words).most_common(target_k * 2)]
        
        if len(candidates) <= target_k:
            return candidates

        # 2. Выборка текста (50 предложений достаточно для оценки структурной роли слов)
        raw_sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        sample_text = " ".join(raw_sentences[:50])
        
        # 3. Жадный алгоритм отбора (Greedy Forward Selection)
        selected = candidates[:3]
        remaining_candidates = candidates[3:]
        target_code = "rr+frf" 
        
        print(f"\n🔍 [FR-Tuning] Запуск топологического отбора базиса (Цель: K={target_k})")
        print(f"   Стартовый каркас (топ-3 частых): {selected}")
        
        while len(selected) < target_k and remaining_candidates:
            best_candidate = None
            max_delta = -1.0
            
            # Вычисляем абсолютный базовый ранг для текущего набора
            base_rank = self._compute_invariant_rank(selected, sample_text, target_code)
            
            for cand in remaining_candidates:
                test_vocab = selected + [cand]
                rank_with = self._compute_invariant_rank(test_vocab, sample_text, target_code)
                
                # Оцениваем чистый прирост новых линейно независимых уравнений (абсолютный ранг)
                delta = rank_with - base_rank
                
                if delta > max_delta:
                    max_delta = delta
                    best_candidate = cand
            
            # Если лучшее слово не добавляет ни одного нового независимого уравнения, останавливаемся
            if max_delta <= 0:
                print(f"   ⚠️ Отбор прерван на шаге {len(selected)}: оставшиеся слова не создают новых алгебраических связей (delta <= 0).")
                break
                
            selected.append(best_candidate)
            remaining_candidates.remove(best_candidate)
            
            # Прогресс-бар для терминала (int(max_delta) корректен, т.к. rank_c - целое число)
            print(f"   [+{len(selected)}/{target_k}] Добавлен узел: «{best_candidate:<10}» | Прирост ранга: +{int(max_delta)}")
            
        print(f"✅ Финальный топологический базис (размер: {len(selected)}): {selected}\n")
        return selected

    @staticmethod
    def _compute_invariant_rank(vocab: List[str], text: str, target_code: str) -> float:
        if len(vocab) < 2:
            return 0.0
            
        word_to_idx = {w: i for i, w in enumerate(vocab)}
        raw_sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        
        relations = []
        for s in raw_sentences:
            s_words = re.findall(r'[а-яёa-z]+', s.lower())
            filtered = [word_to_idx[w] for w in s_words if w in word_to_idx]
            if len(filtered) >= 2:
                relations.append(filtered)
                
        if len(relations) < 2:
            return 0.0
            
        try:
            magnus = MagnusAlgebra(K=len(vocab), degree=4)
            gens = [magnus.expand_word(r) for r in relations]
            solver = HomologySolver(p=10**9 + 7)
            
            code_parts = target_code.split('+')
            M = FRCodeRegistry.build_code(magnus, gens, code_parts)
            res = solver.evaluate(M, dim_f=magnus.dim)
            
            # ВОЗВРАЩАЕМ АБСОЛЮТНЫЙ РАНГ. Это ключ к правильной оценке линейной независимости.
            rank_val = float(res['rank_c'])
            
            del magnus, gens, solver, M, res
            gc.collect()
            
            return rank_val
            
        except Exception:
            return 0.0

    def _build_relations(self, text: str) -> List[List[int]]:
        raw_sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        relations = []
        
        for s in raw_sentences:
            s_words = re.findall(r'[а-яёa-z]+', s.lower())
            filtered = [self.word_to_idx[w] for w in s_words if w in self.word_to_idx]
            if len(filtered) >= 2:
                relations.append(filtered)
                if len(relations) >= self.max_relations:
                    break
                    
        return relations
