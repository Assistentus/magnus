import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from typing import List, Dict, Tuple
from .magnus import MagnusAlgebra

class FRCodeRegistry:
    """
    Универсальный генератор матриц для fr-кодов.
    """
    
    @staticmethod
    def build_code(magnus_alg: MagnusAlgebra, r_generators: List[Dict[int, int]], monomials: List[str]) -> csr_matrix:
        K = magnus_alg.K
        max_deg = magnus_alg.degree
        rows, cols, data = [], [], []
        current_row = 0
        
        def multiply_right(gen_list, right_gens):
            """
            gen_list: список списков [(basis, coeff), ...] — каждый элемент = одна строка
            right_gens: список dict {idx: coeff} — r-генераторы
            """
            new_gen_list = []
            for gen in gen_list:  # gen = одна строка = список (basis, coeff)
                new_gen = []  # новый список для этой строки
                for r_dict in right_gens:
                    for idx_r, coeff_r in r_dict.items():
                        basis_r = magnus_alg.idx_to_basis[idx_r]
                        for basis_curr, coeff_curr in gen:
                            if len(basis_curr) + len(basis_r) <= max_deg:
                                new_basis = basis_curr + basis_r
                                new_gen.append((new_basis, coeff_curr * coeff_r))
                if new_gen:
                    new_gen_list.append(new_gen)
            return new_gen_list

        def multiply_by_f_right(gen_list):
            new_gen_list = []
            for gen in gen_list:
                new_gen = []
                for basis_curr, coeff_curr in gen:
                    if len(basis_curr) + 1 <= max_deg:
                        for a in range(K):
                            new_gen.append((basis_curr + (a,), coeff_curr))
                if new_gen:
                    new_gen_list.append(new_gen)
            return new_gen_list

        for monomial in monomials:
            if not monomial:
                continue
            
            # Начальные генераторы для монома
            if monomial[0] == 'r':
                # Каждое отношение = ОДНА строка = список всех (basis, coeff) из expand_word
                current_gens = []
                for r_dict in r_generators:
                    gen = []
                    for idx, coeff in r_dict.items():
                        gen.append((magnus_alg.idx_to_basis[idx], coeff))
                    if gen:
                        current_gens.append(gen)
            elif monomial[0] == 'f':
                # Каждый f-генератор = одна строка с одним элементом
                current_gens = [[((a,), 1)] for a in range(K)]
            else:
                raise ValueError(f"Недопустимый символ: {monomial[0]}")
            
            # Применяем оставшиеся буквы
            for char in monomial[1:]:
                if char == 'r':
                    current_gens = multiply_right(current_gens, r_generators)
                elif char == 'f':
                    current_gens = multiply_by_f_right(current_gens)
            
            # Добавляем строки в матрицу
            for gen in current_gens:
                for basis, coeff in gen:
                    rows.append(current_row)
                    cols.append(magnus_alg.basis_to_idx[basis])
                    data.append(coeff)
                current_row += 1

        return coo_matrix((data, (rows, cols)), shape=(current_row, magnus_alg.dim), dtype=np.int32).tocsr()

    @staticmethod
    def get_H2_G_Gab(magnus_alg: MagnusAlgebra, r_generators: List[Dict[int, int]]) -> csr_matrix:
        return FRCodeRegistry.build_code(magnus_alg, r_generators, ["rr", "frf", "rff"])

    @staticmethod
    def get_H3_G(magnus_alg: MagnusAlgebra, r_generators: List[Dict[int, int]]) -> csr_matrix:
        return FRCodeRegistry.build_code(magnus_alg, r_generators, ["rr", "frf"])

    @staticmethod
    def get_Tor(magnus_alg: MagnusAlgebra, r_generators: List[Dict[int, int]]) -> csr_matrix:
        return FRCodeRegistry.build_code(magnus_alg, r_generators, ["rff", "frr"])
    
    @staticmethod
    def build_rr_frf_rff(magnus_alg: MagnusAlgebra, r_generators: List[Dict[int, int]]) -> csr_matrix:
        return FRCodeRegistry.get_H2_G_Gab(magnus_alg, r_generators)

    @staticmethod
    def build_rr_frf(magnus_alg: MagnusAlgebra, r_generators: List[Dict[int, int]]) -> csr_matrix:
        return FRCodeRegistry.get_H3_G(magnus_alg, r_generators)
