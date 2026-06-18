import numpy as np
from scipy.sparse import csr_matrix
import gc

# Мягкий импорт Rust-расширения
try:
    from fr_rank_rs import compute_rank_zp_sparse
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False

class HomologySolver:
    """
    ЧТО СЧИТАЕМ: Точный ранг разреженной матрицы над Z_p.
    МАТЕМАТИКА: Использует быстрый Rust-солвер (если доступен в окружении) или
                резервный питоновский метод Гаусса (для совместимости в Open Source).
    ЗАЧЕМ: Дает возможность научному сообществу запускать расчеты без компиляции Rust,
           но сохраняет максимальную производительность при наличии бинарного модуля.
    """
    def __init__(self, p: int = 10**9 + 7):
        self.p = p

    def _compute_rank_zp_python(self, c_matrix: csr_matrix) -> int:
        """
        Математически точный резервный метод Гаусса на чистом Python.
        Оптимизирован для минимизации накладных расходов интерпретатора.
        """
        rows = []
        for r in range(c_matrix.shape[0]):
            start, end = c_matrix.indptr[r], c_matrix.indptr[r+1]
            if start < end:
                # Преобразуем только ненулевые элементы строки в словарь
                d = {int(c): int(v % self.p) for c, v in zip(c_matrix.indices[start:end], c_matrix.data[start:end])}
                d = {c: v for c, v in d.items() if v != 0}
                if d:
                    rows.append(d)
                    
        pivot_col_to_row = {}
        rank = 0
        
        for row in rows:
            while row:
                # Находим ведущий столбец (пивот)
                pivot_c = min(row.keys())
                pivot_val = row[pivot_c]
                
                if pivot_c in pivot_col_to_row:
                    pr = pivot_col_to_row[pivot_c]
                    inv_pivot = pr['inv']
                    factor = (pivot_val * inv_pivot) % self.p
                    
                    # Исключаем элемент
                    for c, val in pr['row'].items():
                        if c in row:
                            new_val = (row[c] - factor * val) % self.p
                            if new_val == 0:
                                del row[c]
                            else:
                                row[c] = new_val
                        else:
                            new_val = (-factor * val) % self.p
                            if new_val != 0:
                                row[c] = new_val
                else:
                    # Новый пивот найден, нормализуем строку
                    inv = pow(pivot_val, self.p - 2, self.p)
                    for c in row:
                        row[c] = (row[c] * inv) % self.p
                    
                    pivot_col_to_row[pivot_c] = {'row': row, 'inv': 1}
                    rank += 1
                    break
        return rank

    def evaluate(self, c_matrix: csr_matrix, dim_f: int) -> dict:
        orig_cols = c_matrix.shape[1]

        if RUST_AVAILABLE:
            # --- БЫСТРЫЙ RUST-ДВИЖОК ---
            # Для Rust выгодно транспонировать высокие матрицы, чтобы уменьшить число столбцов
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
                self.p
            )
            del indptr, indices, data
        else:
            # --- ЧИСТЫЙ PYTHON-ДВИЖОК (FALLBACK) ---
            # ВНИМАНИЕ: Для Python транспонирование ВРЕДНО!
            # Намного выгоднее обрабатывать исходные N строк (обычно 50-100),
            # чем создавать 168 000+ словарей для транспонированных строк.
            # Поэтому здесь мы сознательно НЕ транспонируем матрицу.
            rank = self._compute_rank_zp_python(c_matrix)

        dim_factor = max(0, dim_f - rank)
        nullity = max(0, orig_cols - rank)
        
        del c_matrix
        gc.collect()
        
        return {
            'rank_c': int(rank),
            'dim_f': int(dim_f),
            'dim_factor': int(dim_factor),
            'nullity': int(nullity)
        }
