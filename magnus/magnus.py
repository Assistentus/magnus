
from typing import List, Dict, Tuple

class MagnusAlgebra:
    def __init__(self, K: int, degree: int = 5):
        assert K > 0, "K должно быть > 0"
        assert 1 <= degree <= 6, "Поддерживаются степени усечения от 1 до 6"
        
        self.K = K
        self.degree = degree
        self.basis_to_idx: Dict[Tuple[int, ...], int] = {}
        self.idx_to_basis: List[Tuple[int, ...]] = []
        
        idx = 0
        for deg in range(1, degree + 1):
            if deg == 1:
                for i in range(K):
                    self.basis_to_idx[(i,)] = idx
                    self.idx_to_basis.append((i,))
                    idx += 1
            elif deg == 2:
                for i in range(K):
                    for j in range(K):
                        self.basis_to_idx[(i, j)] = idx
                        self.idx_to_basis.append((i, j))
                        idx += 1
            elif deg == 3:
                for i in range(K):
                    for j in range(K):
                        for k in range(K):
                            self.basis_to_idx[(i, j, k)] = idx
                            self.idx_to_basis.append((i, j, k))
                            idx += 1
            elif deg == 4:
                for i in range(K):
                    for j in range(K):
                        for k in range(K):
                            for l in range(K):
                                self.basis_to_idx[(i, j, k, l)] = idx
                                self.idx_to_basis.append((i, j, k, l))
                                idx += 1
            elif deg == 5:
                for i in range(K):
                    for j in range(K):
                        for k in range(K):
                            for l in range(K):
                                for m in range(K):
                                    self.basis_to_idx[(i, j, k, l, m)] = idx
                                    self.idx_to_basis.append((i, j, k, l, m))
                                    idx += 1
            elif deg == 6:
                for i in range(K):
                    for j in range(K):
                        for k in range(K):
                            for l in range(K):
                                for m in range(K):
                                    for n in range(K):
                                        self.basis_to_idx[(i, j, k, l, m, n)] = idx
                                        self.idx_to_basis.append((i, j, k, l, m, n))
                                        idx += 1
                            
        self.dim = idx
        expected_dim = sum(K**i for i in range(1, degree + 1))
        assert self.dim == expected_dim, f"Ошибка размерности: {self.dim} != {expected_dim}"

    def expand_word(self, word_indices: List[int]) -> Dict[int, int]:
        assert all(0 <= w < self.K for w in word_indices), "Индексы вне диапазона [0, K-1]"
        degs = [{} for _ in range(self.degree + 1)]
        
        for w in word_indices:
            for d in range(self.degree, 1, -1):
                for prev_basis, count in degs[d-1].items():
                    new_basis = prev_basis + (w,)
                    degs[d][new_basis] = degs[d].get(new_basis, 0) + count
            
            degs[1][(w,)] = degs[1].get((w,), 0) + 1
            
        result = {}
        for d in range(1, self.degree + 1):
            for basis, count in degs[d].items():
                result[self.basis_to_idx[basis]] = count
            
        return result


