# magnus/presentation.py
import re
from collections import Counter
from typing import List, Optional

from .magnus import MagnusAlgebra
from .codes import FRCodeRegistry
from .solver import HomologySolver

from fr_rank_rs import select_homological_generators


class TextPresentation:
    """
    Копредставление группы G = <V | R>, порожденное текстом.

    Математика:
      - V (образующие) выбираются по их топологической значимости
        (приросту абсолютного ранга) через Rust-greedy.
      - R (отношения) строятся на основе отобранных узлов V.

    Зачем:
      Избежать «алгебраической воды» и построить триангуляцию вокруг
      истинных смысловых хабов, игнорируя частотный шум.
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

    # ============================================================
    # ОТБОР БАЗИСА (через Rust-greedy)
    # ============================================================

    def _select_homological_generators(self, text: str, target_k: int) -> List[str]:
        # 1. Пул кандидатов: слова длиной >= 2
        words = re.findall(r'[а-яёa-z]+', text.lower())
        valid_words = [w for w in words if len(w) >= 2]
        candidates = [w for w, _ in Counter(valid_words).most_common(target_k * 2)]

        if len(candidates) <= target_k:
            return candidates

        # 2. Выборка предложений для оценки структурной роли слов
        raw_sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        sample_text = " ".join(raw_sentences[:50])

        # 3. Токенизация один раз
        sentences_tokens = []
        for s in re.split(r'(?<=[.!?])\s+|\n+', sample_text):
            toks = re.findall(r'[а-яёa-z]+', s.lower())
            sentences_tokens.append(toks)

        # 4. Для каждого кандидата — relations, в которых он участвует
        cand_to_idx = {w: i for i, w in enumerate(candidates)}
        candidates_relations = []
        for cand in candidates:
            rels = []
            for toks in sentences_tokens:
                if cand not in toks:
                    continue
                idxs = [cand_to_idx[t] for t in toks if t in cand_to_idx]
                if len(idxs) >= 2:
                    rels.append(idxs)
            candidates_relations.append(rels)

        # 5. Жадный отбор — в Rust
        print(f"\n🔍 [FR-Tuning] Топологический отбор (Rust, K={target_k})")
        selected = select_homological_generators(
            candidates_relations,
            target_k,
            4,                 # degree
            ["rr", "frf"],     # code
            10**9 + 7,
            3,                 # initial_selected
        )

        final = [candidates[i] for i in selected]
        print(f"✅ Финальный базис ({len(final)}): {final}\n")
        return final

    # ============================================================
    # СБОРКА ОТНОШЕНИЙ
    # ============================================================

    def _build_relations(self, text: str) -> List[List[int]]:
        raw_sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        relations = []

        for s in raw_sentences:
            s_words = re.findall(r'[а-яёa-z]+', s.lower())
            filtered = [self.word_to_idx[w] for w in s_words
                        if w in self.word_to_idx]
            if len(filtered) >= 2:
                relations.append(filtered)
                if len(relations) >= self.max_relations:
                    break

        return relations
