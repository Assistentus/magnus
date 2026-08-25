import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from typing import List, Dict, Tuple
from .magnus import MagnusAlgebra

def _get_basis(magnus_alg, idx):
    """Совместимость: работает со списком, методом и property"""
    attr = magnus_alg.idx_to_basis
    if callable(attr):
        return attr(idx)
    else:
        return attr[idx]

def _get_idx(magnus_alg, basis):
    """Совместимость: работает со словарем, методом и property"""
    attr = magnus_alg.basis_to_idx
    if callable(attr):
        return attr(basis)
    else:
        return attr[basis]


class FRCodeRegistry:
    """
    Универсальный генератор матриц для fr-кодов.
    Совместим с MagnusAlgebra (старой и новой).
    """
    
    @staticmethod
    def build_code(magnus_alg: MagnusAlgebra, r_generators: List[Dict[int, int]], monomials: List[str]) -> csr_matrix:
        K = magnus_alg.K
        max_deg = magnus_alg.degree
        P = 10**9 + 7
        rows, cols, data = [], [], []
        current_row = 0
        
        # Безопасные хелперы для вызова (поддерживают и методы (), и словари [])
        def get_basis(idx):
            return magnus_alg.idx_to_basis(idx) if callable(magnus_alg.idx_to_basis) else magnus_alg.idx_to_basis[idx]
            
        def get_idx(basis):
            return magnus_alg.basis_to_idx(basis) if callable(magnus_alg.basis_to_idx) else magnus_alg.basis_to_idx[basis]

        def multiply_right(gen_list, right_gens):
            new_gen_list = []
            for gen in gen_list:
                new_gen = []
                for r_dict in right_gens:
                    for idx_r, coeff_r in r_dict.items():
                        basis_r = get_basis(idx_r)  # <--- ИСПРАВЛЕНО
                        for basis_curr, coeff_curr in gen:
                            if len(basis_curr) + len(basis_r) <= max_deg:
                                new_basis = basis_curr + basis_r
                                new_coeff = (coeff_curr * coeff_r) % P
                                if new_coeff != 0:
                                    new_gen.append((new_basis, new_coeff))
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
                            new_gen.append((basis_curr + (a,), coeff_curr % P))
                if new_gen:
                    new_gen_list.append(new_gen)
            return new_gen_list

        for monomial in monomials:
            if not monomial:
                continue
            
            if monomial[0] == 'r':
                current_gens = []
                for r_dict in r_generators:
                    gen = []
                    for idx, coeff in r_dict.items():
                        if (coeff % P) != 0:
                            gen.append((get_basis(idx), coeff % P))  # <--- ИСПРАВЛЕНО
                    if gen:
                        current_gens.append(gen)
            elif monomial[0] == 'f':
                current_gens = [[((a,), 1)] for a in range(K)]
            else:
                raise ValueError(f"Недопустимый символ: {monomial[0]}")
            
            for char in monomial[1:]:
                if char == 'r':
                    current_gens = multiply_right(current_gens, r_generators)
                elif char == 'f':
                    current_gens = multiply_by_f_right(current_gens)
            
            for gen in current_gens:
                for basis, coeff in gen:
                    c_mod = coeff % P
                    if c_mod != 0:
                        rows.append(current_row)
                        cols.append(get_idx(basis))  # <--- ИСПРАВЛЕНО
                        data.append(c_mod)
                current_row += 1

        return coo_matrix((data, (rows, cols)), shape=(current_row, magnus_alg.dim), dtype=np.int64).tocsr()

    @staticmethod
    def get_H2_G_Gab(magnus_alg, r_generators):
        return FRCodeRegistry.build_code(magnus_alg, r_generators, ["rr", "frf", "rff"])

    @staticmethod
    def get_H3_G(magnus_alg, r_generators):
        return FRCodeRegistry.build_code(magnus_alg, r_generators, ["rr", "frf"])

    @staticmethod
    def get_Tor(magnus_alg, r_generators):
        return FRCodeRegistry.build_code(magnus_alg, r_generators, ["rff", "frr"])
    
    @staticmethod
    def build_rr_frf_rff(magnus_alg, r_generators):
        return FRCodeRegistry.get_H2_G_Gab(magnus_alg, r_generators)

    @staticmethod
    def build_rr_frf(magnus_alg, r_generators):
        return FRCodeRegistry.get_H3_G(magnus_alg, r_generators)
