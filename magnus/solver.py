import numpy as np
from scipy.sparse import csr_matrix
import gc

from fr_rank_rs import compute_rank_zp_sparse


class HomologySolver:
    """
    Точный ранг разреженной матрицы над Z_p.

    Вычислительное ядро — Rust (`compute_rank_zp_sparse`).
    Python-fallback удалён: если Rust-модуль не собран,
    библиотека не работает.
    """

    def __init__(self, p: int = 10**9 + 7):
        self.p = p

    def evaluate(self, c_matrix: csr_matrix, dim_f: int) -> dict:
        orig_cols = c_matrix.shape[1]
        if c_matrix.shape[0] > c_matrix.shape[1]:
            c_matrix = c_matrix.T.tocsr()
            gc.collect()

        indptr = c_matrix.indptr.astype(np.int64, copy=False)
        indices = c_matrix.indices.astype(np.int64, copy=False)
        data = c_matrix.data.astype(np.int64, copy=False)

        rank = compute_rank_zp_sparse(
            indptr,
            indices,
            data,
            c_matrix.shape[1],
            self.p,
        )

        dim_factor = max(0, dim_f - rank)
        nullity = max(0, orig_cols - rank)

        return {
            'rank_c': int(rank),
            'dim_f': int(dim_f),
            'dim_factor': int(dim_factor),
            'nullity': int(nullity),
        }
