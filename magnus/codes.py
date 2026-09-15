# magnus/codes.py
import numpy as np
from scipy.sparse import csr_matrix

from fr_rank_rs import build_fr_code_csr


class FRCodeRegistry:
    """
    Построение матриц fr-кодов.

    ВАЖНО: сигнатура `build_code` теперь принимает `relations` —
    список исходных слов (list of list of int), а не разложенные
    многочлены. Раскрытие делает Rust внутри `build_fr_code_csr`.
    """

    @staticmethod
    def build_code(magnus_alg, relations, monomials) -> csr_matrix:
        """
        Построить матрицу fr-кода.

        Args:
            magnus_alg: MagnusAlgebra (используются только K и degree)
            relations: List[List[int]] — исходные слова
            monomials: List[str] — например ['rr', 'frf']

        Returns:
            csr_matrix размера (n_rows, dim_f)
        """
        indptr, indices, data, n_rows, n_cols = build_fr_code_csr(
            [list(r) for r in relations],
            list(monomials),
            magnus_alg.K,
            magnus_alg.degree,
            10**9 + 7,
        )

        return csr_matrix(
            (
                np.asarray(data, dtype=np.int64),
                np.asarray(indices, dtype=np.int64),
                np.asarray(indptr, dtype=np.int64),
            ),
            shape=(n_rows, n_cols),
        )

    # ---- Удобные обёртки для конкретных кодов ----

    @staticmethod
    def get_H2_G_Gab(magnus_alg, relations) -> csr_matrix:
        return FRCodeRegistry.build_code(
            magnus_alg, relations, ["rr", "frf", "rff"],
        )

    @staticmethod
    def get_H3_G(magnus_alg, relations) -> csr_matrix:
        return FRCodeRegistry.build_code(
            magnus_alg, relations, ["rr", "frf"],
        )

    @staticmethod
    def get_Tor(magnus_alg, relations) -> csr_matrix:
        return FRCodeRegistry.build_code(
            magnus_alg, relations, ["rff", "frr"],
        )

    @staticmethod
    def build_rr_frf(magnus_alg, relations) -> csr_matrix:
        return FRCodeRegistry.build_code(magnus_alg, relations, ["rr", "frf"])

    @staticmethod
    def build_rr_frf_rff(magnus_alg, relations) -> csr_matrix:
        return FRCodeRegistry.build_code(
            magnus_alg, relations, ["rr", "frf", "rff"],
        )
