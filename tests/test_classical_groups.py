#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

# 1. Автоматическая настройка путей для абсолютной совместимости (локально и в GitHub Actions CI/CD)
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
parent_dir = root_dir.parent

for d in [str(root_dir), str(parent_dir)]:
    if d not in sys.path:
        sys.path.insert(0, d)

# 2. Универсальный импорт компонентов библиотеки magnus
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

import pytest


def test_free_group_verification():
    """
    ВЕРИФИКАЦИЯ 1: Свободная группа F_K (отношений нет, R = empty).
    
    Теоретический факт (Иванов и др., 2020): 
    Если R = empty, то идеал отношений r = 0.
    Ожидаемый результат: rank(Mc) == 0, dim_factor == dim_f.
    """
    K = 5
    magnus = MagnusAlgebra(K=K, degree=3)
    
    r_generators = []
    c_matrix = FRCodeRegistry.build_rr_frf(magnus, r_generators)
    solver = HomologySolver(p=10**9 + 7)
    res = solver.evaluate(c_matrix, dim_f=magnus.dim)
    
    assert res['rank_c'] == 0, "Ранг свободной группы без отношений должен быть строго равен 0"
    assert res['dim_factor'] == magnus.dim, "Размерность фактора должна быть равна полной размерности свободного пространства dim(f)"


def test_cyclic_group_verification():
    """
    ВЕРИФИКАЦИЯ 2: Циклическая группа Z_n = < x | x^n >.
    
    Теоретический факт: 
    K = 1 генератор, 1 отношение = x^n. 
    Ожидаемый результат: rank(Mc) == 1 над Z_p.
    """
    K = 1
    n = 5
    magnus = MagnusAlgebra(K=K, degree=3)
    
    rel = [0] * n
    r_generators = [magnus.expand_word(rel)]
    
    c_matrix = FRCodeRegistry.build_code(magnus, r_generators, ["r"])
    solver = HomologySolver(p=10**9 + 7)
    res = solver.evaluate(c_matrix, dim_f=magnus.dim)
    
    assert res['rank_c'] == 1, "Ранг матрицы идеала r для циклической группы Z_5 должен быть строго равен 1"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
