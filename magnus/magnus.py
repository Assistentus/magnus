# magnus/magnus.py
from typing import List

from fr_rank_rs import magnus_expand_word


class MagnusAlgebra:
    """
    Магнус-алгебра: раскрытие слов в разреженный вектор над Z_p.

    Все вычисления — в Rust (`magnus_expand_word`).
    Python-обёртка даёт удобный dict-интерфейс.
    """

    def __init__(self, K: int, degree: int = 5):
        assert K > 0, "K должно быть > 0"
        assert degree >= 1, "degree должно быть >= 1"
        self.K = K
        self.degree = degree

    @property
    def dim(self) -> int:
        """Полная размерность свободного пространства f."""
        total, power = 0, 1
        for _ in range(self.degree):
            power *= self.K
            total += power
        return total

    def expand_word(self, word_indices: List[int]) -> dict:
        """
        Раскрытие слова в разреженный вектор.

        Возвращает dict {idx: coeff}.
        """
        pairs = magnus_expand_word(
            list(word_indices), self.K, self.degree, 10**9 + 7,
        )
        return {int(idx): int(coeff) for idx, coeff in pairs}

    def basis_to_idx(self, basis) -> int:
        """
        Индекс монома по базису. Оставлено для отладки и тестов.
        """
        d = len(basis)
        assert 1 <= d <= self.degree, f"Степень {d} вне [1, {self.degree}]"
        offset = sum(self.K ** i for i in range(1, d))
        idx = 0
        for v in basis:
            assert 0 <= v < self.K
            idx = idx * self.K + v
        return offset + idx
