import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from typing import List, Dict, Tuple
from .magnus import MagnusAlgebra

class FRCodeRegistry:
    """
    Универсальный генератор матриц для ЛЮБЫХ fr-кодов.
    """
    
    @staticmethod
    def build_code(magnus_alg: MagnusAlgebra, r_generators: List[Dict[int, int]], monomials: List[str]) -> csr_matrix:
        K = magnus_alg.K
        max_deg = magnus_alg.degree
        rows, cols, data = [], [], []
        current_row = 0
        
        def multiply_right(gen_list: List[Tuple[Tuple[int, ...], int]], right_gens: List[Dict[int, int]]) -> List[Tuple[Tuple[int, ...], int]]:
            new_gens = []
            for basis_curr, coeff_curr in gen_list:
                for r_dict in right_gens:
                    for idx_r, coeff_r in r_dict.items():
                        basis_r = magnus_alg.idx_to_basis[idx_r]
                        if len(basis_curr) + len(basis_r) <= max_deg:
                            new_basis = basis_curr + basis_r
                            new_gens.append((new_basis, coeff_curr * coeff_r))
            return new_gens

        def multiply_by_f_right(gen_list: List[Tuple[Tuple[int, ...], int]]) -> List[Tuple[Tuple[int, ...], int]]:
            new_gens = []
            for basis_curr, coeff_curr in gen_list:
                if len(basis_curr) + 1 <= max_deg:
                    for a in range(K):
                        new_gens.append((basis_curr + (a,), coeff_curr))
            return new_gens

        for monomial in monomials:
            if not monomial:
                continue
                
            if monomial[0] == 'r':
                current_gens = []
                for r_dict in r_generators:
                    for idx, coeff in r_dict.items():
                        current_gens.append((magnus_alg.idx_to_basis[idx], coeff))
            elif monomial[0] == 'f':
                current_gens = [((a,), 1) for a in range(K)]
            else:
                raise ValueError(f"Недопустимый символ: {monomial[0]}")
            
            for char in monomial[1:]:
                if char == 'r':
                    current_gens = multiply_right(current_gens, r_generators)
                elif char == 'f':
                    current_gens = multiply_by_f_right(current_gens)
                else:
                    raise ValueError(f"Недопустимый символ: {char}")
            
            for basis, coeff in current_gens:
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
    
    # ========================================================================
    # СИНОНИМЫ (АЛИАСЫ) ДЛЯ СОВМЕСТИМОСТИ С ТЕСТАМИ И ЭКСПЕРИМЕНТАМИ
    # ========================================================================
    @staticmethod
    def build_rr_frf_rff(magnus_alg: MagnusAlgebra, r_generators: List[Dict[int, int]]) -> csr_matrix:
        """Инвариант H2_G_Gab (Теорема 5)"""
        return FRCodeRegistry.get_H2_G_Gab(magnus_alg, r_generators)

    @staticmethod
    def build_rr_frf(magnus_alg: MagnusAlgebra, r_generators: List[Dict[int, int]]) -> csr_matrix:
        """Инвариант H3_G"""
        return FRCodeRegistry.get_H3_G(magnus_alg, r_generators)
