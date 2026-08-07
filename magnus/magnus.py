from typing import List, Dict, Tuple
import itertools

class MagnusAlgebra:
    def __init__(self, K: int, degree: int = 5):
        """
        Оптимизированная версия:
        - Не генерирует базис заранее
        - Использует product() вместо вложенных циклов
        - Вычисляет индекс на лету через формулу
        - Поддерживает ЛЮБОЕ degree (ограничено только памятью)
        """
        assert K > 0, "K должно быть > 0"
        assert degree >= 1, "degree должно быть >= 1"
        
        self.K = K
        self.degree = degree
        
        # Предвычисляем смещения для быстрого вычисления индекса
        # dim_d = K^d — размерность степени d
        # offset_d = sum(K^i for i=1..d-1) — смещение для степени d
        self.offsets = [0]  # offsets[d] = начало степени d
        total = 0
        for d in range(1, degree + 1):
            self.offsets.append(total)
            total += K ** d
        
        self.dim = total
        self._basis_cache = {}  # Кеш для часто используемых кортежей
    
    def basis_to_idx(self, basis: Tuple[int, ...]) -> int:
        """
        Вычисляет индекс базисного элемента на лету (O(len(basis))).
        Не требует хранения всего базиса в памяти!
        """
        d = len(basis)
        if d == 0 or d > self.degree:
            raise ValueError(f"Степень {d} вне диапазона [1, {self.degree}]")
        
        # Смещение для этой степени
        offset = self.offsets[d]
        
        # Индекс внутри степени: basis[0]*K^{d-1} + basis[1]*K^{d-2} + ... + basis[d-1]
        idx = 0
        for i, val in enumerate(basis):
            idx = idx * self.K + val
        
        return offset + idx
    
    def idx_to_basis(self, idx: int) -> Tuple[int, ...]:
        """Восстанавливает базис по индексу (тоже на лету)"""
        # Находим степень
        for d in range(1, self.degree + 1):
            size = self.K ** d
            if idx < self.offsets[d] + size:
                local_idx = idx - self.offsets[d]
                # Конвертируем в K-ичную систему
                basis = []
                temp = local_idx
                for _ in range(d):
                    basis.append(temp % self.K)
                    temp //= self.K
                return tuple(reversed(basis))
        
        raise ValueError(f"Индекс {idx} вне диапазона")
    
    def expand_word(self, word_indices: List[int]) -> Dict[int, int]:
        """
        Оптимизированное разложение слова с вычислением индексов на лету.
        """
        assert all(0 <= w < self.K for w in word_indices), "Индексы вне диапазона [0, K-1]"
        
        # Используем словарь {базис: счет} для эффективности
        degs = [{} for _ in range(self.degree + 1)]
        
        for w in word_indices:
            # Обновляем от старшей степени к младшей
            for d in range(self.degree, 1, -1):
                for prev_basis, count in degs[d-1].items():
                    new_basis = prev_basis + (w,)
                    degs[d][new_basis] = degs[d].get(new_basis, 0) + count
            
            # Степень 1
            degs[1][(w,)] = degs[1].get((w,), 0) + 1
        
        # Конвертируем в {индекс: счет}
        result = {}
        for d in range(1, self.degree + 1):
            for basis, count in degs[d].items():
                result[self.basis_to_idx(basis)] = count
        
        return result



