#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path
import random

# 1. Автоматическая настройка путей импорта (локально и в GitHub Actions CI/CD)
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


def test_dihedral_group_D4_non_commutative():
    """
    НЕТРИВИАЛЬНЫЙ ТЕСТ 1: Некоммутативная группа Диэдра D_4.
    Задание: G = < r, s | r^4 = 1, s^2 = 1, s*r*s*r = 1 >
    K = 2 генератора: r (индекс 0), s (индекс 1).
    """
    K = 2
    magnus = MagnusAlgebra(K=K, degree=4)
    
    # Отношения группы D_4:
    rel_r4 = [0, 0, 0, 0]        # r^4 = 1
    rel_s2 = [1, 1]              # s^2 = 1
    rel_srsr = [1, 0, 1, 0]      # s*r*s*r = 1
    
    relations = [rel_r4, rel_s2, rel_srsr]
    r_generators = [magnus.expand_word(rel) for rel in relations]
    
    solver = HomologySolver(p=10**9 + 7)
    
    # Считаем матрицу кода c1 = rr + frf + rff (Инвариант H2)
    c1_matrix = FRCodeRegistry.build_rr_frf_rff(magnus, r_generators)
    res1 = solver.evaluate(c1_matrix, dim_f=magnus.dim)
    
    print(f"\n   * [D4] Ранг матрицы идеала c1: {res1['rank_c']}")
    print(f"   * [D4] dim(f/c1) = {res1['dim_factor']} (должно быть >= K={K})")
    
    # Для D_4 ранг матрицы нетривиален из-за взаимодействия некоммутативных членов
    assert res1['rank_c'] > 0, "Ранг группы D_4 должен быть строго больше 0"
    assert res1['dim_factor'] >= K, "Инвариант dim_factor >= K должен выполняться для D_4"


def test_random_sequence_invariant_stress():
    """
    НЕТРИВИАЛЬНЫЙ ТЕСТ 2: Стресс-тест инвариантов на СЛУЧАЙНЫХ последовательностях.
    Проверяет, что алгебраическое неравенство dim(f/c2) >= dim(f/c1) >= K 
    выполняется абсолютным образом на ЛЮБЫХ рандомных данных.
    """
    K = 8
    magnus = MagnusAlgebra(K=K, degree=3)
    solver = HomologySolver(p=10**9 + 7)
    
    random.seed(42)
    
    # Генерируем 3 случайных набора отношений
    for trial in range(3):
        num_relations = random.randint(5, 12)
        relations = [
            [random.randint(0, K - 1) for _ in range(random.randint(2, 5))]
            for _ in range(num_relations)
        ]
        
        r_generators = [magnus.expand_word(rel) for rel in relations]
        
        # c1 = rr + frf + rff
        c1_matrix = FRCodeRegistry.build_rr_frf_rff(magnus, r_generators)
        res1 = solver.evaluate(c1_matrix, dim_f=magnus.dim)
        
        # c2 = rr + frf
        c2_matrix = FRCodeRegistry.build_rr_frf(magnus, r_generators)
        res2 = solver.evaluate(c2_matrix, dim_f=magnus.dim)
        
        print(f"\n   * [Trial {trial+1}] dim(f/c1) = {res1['dim_factor']} | dim(f/c2) = {res2['dim_factor']}")
        
        # Проверка фундаментальных инвариантов:
        assert res1['dim_factor'] >= K, f"Trial {trial}: dim_factor(c1) < K"
        assert res2['dim_factor'] >= res1['dim_factor'], f"Trial {trial}: dim_factor(c2) < dim_factor(c1)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
