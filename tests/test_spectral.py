#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

# 1. Автоматическая настройка путей импорта (локально и в GitHub Actions CI/CD)
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
parent_dir = root_dir.parent

for d in [str(root_dir), str(parent_dir)]:
    if d not in sys.path:
        sys.path.insert(0, d)

# 2. Универсальный каскад импортов для любых условий окружения
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


def build_coproduct_presentation(relations_R: list, K: int):
    """
    Строит свободное произведение двух копий одного представления: c ⊔ c = F_1 * F_2 -> G.
    Генераторы 1-й копии: 0 .. K-1
    Генераторы 2-й копии: K .. 2*K-1
    """
    K_coprod = 2 * K
    relations_coprod = []
    
    # 1. Первая копия c (индексы 0..K-1)
    for r in relations_R:
        relations_coprod.append(r)
        
    # 2. Вторая копия c (индексы сдвинуты на +K)
    for r in relations_R:
        shifted_r = [idx + K for idx in r]
        relations_coprod.append(shifted_r)
        
    return K_coprod, relations_coprod


def test_adams_e1_page_differential():
    """
    ТЕСТ: Расчет колонок E_1^{0, q} и E_1^{1, q} первого листа E_1 
    косимплициального комплекса B(c) спектральной последовательности (Thm 2.12, Иванов и др., 2020).
    """
    print("\n" + "="*80)
    print("🌌 СБОРКА 1-ГО ЛИСТА E_1 СПЕКТРАЛЬНОЙ ПОСЛЕДОВАТЕЛЬНОСТИ (B(c) COMPLEX)")
    print("="*80)
    
    # Представление циклической группы Z_3 = < x | x^3 >
    K = 1
    rel = [0, 0, 0]  # x^3 = 1
    relations_R = [rel]
    
    # --- ЭТАП 1: Нулевая колонка E_1^{0, q} = (f/c)(c) ---
    magnus_0 = MagnusAlgebra(K=K, degree=3)
    gens_0 = [magnus_0.expand_word(r) for r in relations_R]
    c_matrix_0 = FRCodeRegistry.build_rr_frf(magnus_0, gens_0)
    
    solver = HomologySolver(p=10**9 + 7)
    res_0 = solver.evaluate(c_matrix_0, dim_f=magnus_0.dim)
    print(f"   * [E1^(0)] Базовое свободное пространство: {res_0['dim_f']}")
    print(f"   * [E1^(0)] Ранг базового кода c(G):          {res_0['rank_c']}")
    print(f"   * [E1^(0)] Размерность E1^(0) = (f/c)(G):      {res_0['dim_factor']}")
    
    # --- ЭТАП 2: Первая колонка E_1^{1, q} = (f/c)(c ⊔ c) ---
    K_coprod, rel_coprod = build_coproduct_presentation(relations_R, K)
    magnus_1 = MagnusAlgebra(K=K_coprod, degree=3)
    gens_1 = [magnus_1.expand_word(r) for r in rel_coprod]
    c_matrix_1 = FRCodeRegistry.build_rr_frf(magnus_1, gens_1)
    
    res_1 = solver.evaluate(c_matrix_1, dim_f=magnus_1.dim)
    print(f"\n   * [E1^(1)] Копроизведение c ⊔ c (K'={K_coprod}):")
    print(f"   * [E1^(1)] Свободное пространство (c ⊔ c):  {res_1['dim_f']}")
    print(f"   * [E1^(1)] Ранг c(G ⊔ G):                   {res_1['rank_c']}")
    print(f"   * [E1^(1)] Размерность E1^(1) = (f/c)(G*G):    {res_1['dim_factor']}")
    
    # Алгебраические проверки
    assert res_0['dim_factor'] > 0
    assert res_1['dim_factor'] > res_0['dim_factor']
    print("\n   [УСПЕХ] Первый лист E_1 спектральной последовательности собран и верифицирован!")
    print("="*80 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
