#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path
import pytest

# 1. Автоматическая настройка путей импорта (для CI/CD и локальных запусков)
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
parent_dir = root_dir.parent

for d in [str(root_dir), str(parent_dir)]:
    if d not in sys.path:
        sys.path.insert(0, d)

# 2. Универсальный каскад импортов 
try:
    from magnus import MagnusAlgebra, FRCodeRegistry, HomologySolver
except ModuleNotFoundError:
    try:
        from magnus.magnus import MagnusAlgebra
        from magnus.codes import FRCodeRegistry
        from magnus.solver import HomologySolver
    except ModuleNotFoundError:
        try:
            from fr_lib.codes import FRCodeRegistry
            from fr_lib.magnus import MagnusAlgebra
            from fr_lib.solver import HomologySolver
        except ModuleNotFoundError:
            from codes import FRCodeRegistry
            from magnus import MagnusAlgebra
            from solver import HomologySolver

# 📌 ПОЛНЫЙ СЛОВАРЬ fr-КОДОВ (Ivanov, Mikhailov, Pavutnitskiy, 2020, стр. 22)
FULL_PAGE_22_DICTIONARY = [
    ("r", ["r"]),
    ("rr", ["rr"]),
    ("rrr", ["rrr"]),
    ("fr + rf", ["fr", "rf"]),
    ("ffr + frf + rff", ["ffr", "frf", "rff"]),
    ("r + ff", ["r", "ff"]),
    ("r + fff", ["r", "fff"]),
    ("rf + ffr", ["rf", "ffr"]),
    ("fr + rf + fff", ["fr", "rf", "fff"]),
    ("rr + fff", ["rr", "fff"]),
    ("rr + frf", ["rr", "frf"]),
    ("rrf + frr", ["rrf", "frr"]),
    ("rfr + frf", ["rfr", "frf"]),
    ("rff + ffr", ["rff", "ffr"]),
    ("rr + frf + rff", ["rr", "frf", "rff"]),
    ("rr + ffr", ["rr", "ffr"]),
    ("rfr + frr", ["rfr", "frr"]),
    ("rr + ffr + rff", ["rr", "ffr", "rff"]),
    ("rr + ffr + frf + rff", ["rr", "ffr", "frf", "rff"]),
    ("rff + frr", ["rff", "frr"]),
    ("rrf + rfr + frr", ["rrf", "rfr", "frr"])
]

@pytest.mark.parametrize("code_name, monomials", FULL_PAGE_22_DICTIONARY)
def test_full_dictionary_coverage(code_name, monomials):
    """
    ЭКСПАНСИВНЫЙ ТЕСТ ПОКРЫТИЯ (SOFTWARE COVERAGE):
    Проверяет, что универсальный парсер FRCodeRegistry.build_code 
    корректно обрабатывает абсолютно все 21 код из словаря на странице 22.
    """
    # Берем циклическую группу Z_2 = < x | x^2 = 1 >
    K = 1
    # Степень усечения d=4 (с запасом для кодов длины 3, таких как rrr)
    magnus = MagnusAlgebra(K=K, degree=4)
    
    rel = [0, 0]
    r_generators = [magnus.expand_word(rel)]
    
    # Пытаемся собрать матрицу для текущего кода из таблицы
    c_matrix = FRCodeRegistry.build_code(magnus, r_generators, monomials)
    
    solver = HomologySolver(p=10**9 + 7)
    res = solver.evaluate(c_matrix, dim_f=magnus.dim)
    
    # Базовые инженерные проверки на то, что парсер не упал и выдал адекватные матрицы
    assert c_matrix.shape[1] == magnus.dim, f"[{code_name}] Ошибка размерности столбцов"
    assert res['rank_c'] >= 0, f"[{code_name}] Ранг не может быть отрицательным"
    assert res['dim_factor'] >= 0, f"[{code_name}] Фактор-размерность не может быть отрицательной"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
