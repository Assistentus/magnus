#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pytest
from magnus import TextPresentation, MagnusAlgebra, FRCodeRegistry, HomologySolver

def test_theorem_5_invariants_degree_4():
    """
    МАТЕМАТИЧЕСКОЕ ДОКАЗАТЕЛЬСТВО В КОДЕ (Степень 4):
    
    Инвариант 1: Поскольку код c1 = rr + frf + rff состоит из мономов длины >= 2, 
    он содержится в f^2. Следовательно, f/c1 сюръективно отображается на f/f^2.
    Размерность f/f^2 равна K. Поэтому СТРОГИЙ ИНВАРИАНТ: dim_factor(c1) >= K.
    (На малых текстах пространство может не насыщаться полностью, давая > K, 
    но на больших текстах оно стремится к K).
    
    Инвариант 2: Код c2 = rr + frf является подмножеством c1 (c2 ⊂ c1).
    Следовательно, существует сюръекция f/c2 -> f/c1.
    СТРОГИЙ ИНВАРИАНТ: dim_factor(c2) >= dim_factor(c1).
    """
    text = "Он вошел в комнату. Он не знал, что делать. В комнате было темно. " \
           "Что он будет делать дальше? Он сел на стул. Стул был старый. " \
           "В старом стуле была тайна. Тайна не давала ему спать. " \
           "Он не мог спать. Он думал о тайне. Тайна была в комнате."
    
    K = 15
    
    print("\n" + "="*80)
    print("ЗАПУСК ДИАГНОСТИЧЕСКОГО ТЕСТА: АЛГЕБРАИЧЕСКИЕ ИНВАРИАНТЫ (Степень 4)")
    print("="*80)
    
    pres = TextPresentation(text, k_vocab=K, max_relations=50)
    
    if len(pres.relations) > 5:
        print(f"   [+] Копредставление группы построено. Найдено отношений: {len(pres.relations)}")
    else:
        print(f"  Х ОШИБКА: Слишком мало отношений для проведения теста ({len(pres.relations)})")
        assert len(pres.relations) > 5, "Недостаточно отношений для проверки"
    
    magnus = MagnusAlgebra(K=K, degree=4)
    print(f"   [+] Базис Магнуса инициализирован. Размерность свободного пространства f: {magnus.dim}")
    
    r_generators = [magnus.expand_word(rel) for rel in pres.relations]
    solver = HomologySolver(p=10**9 + 7)

    failures = []
    
    print("\n--- ЭТАП 1: Анализ кода c1 = rr + frf + rff (Инвариант H2) ---")
    c1_matrix = FRCodeRegistry.build_rr_frf_rff(magnus, r_generators)
    res1 = solver.evaluate(c1_matrix, dim_f=magnus.dim)
    
    dim_factor_1 = res1['dim_factor']
    print(f"   * dim(f / c1) = {dim_factor_1}")
    
    if dim_factor_1 >= K:
        print(f"   [УСПЕХ] Инвариант 1 соблюден: dim_factor ({dim_factor_1}) >= K ({K})")
    else:
        err_msg = f"Инвариант 1 НАРУШЕН: dim_factor ({dim_factor_1}) оказался меньше K ({K})"
        print(f"   [КРИТИЧЕСКАЯ ОШИБКА] {err_msg}")
        failures.append(err_msg)

    print("\n--- ЭТАП 2: Анализ кода c2 = rr + frf (Инвариант H3) ---")
    c2_matrix = FRCodeRegistry.build_rr_frf(magnus, r_generators)
    res2 = solver.evaluate(c2_matrix, dim_f=magnus.dim)
    
    dim_factor_2 = res2['dim_factor']
    print(f"   * dim(f / c2) = {dim_factor_2}")
    

    if dim_factor_2 >= dim_factor_1:
        print(f"   [УСПЕХ] Инвариант 2 соблюден: dim_factor_c2 ({dim_factor_2}) >= dim_factor_c1 ({dim_factor_1})")
    else:
        err_msg = f"Инвариант 2 НАРУШЕН: фактор под-идеала c2 ({dim_factor_2}) меньше фактора c1 ({dim_factor_1})"
        print(f"   [КРИТИЧЕСКАЯ ОШИБКА] {err_msg}")
        failures.append(err_msg)

    print("\n" + "="*80)
    if not failures:
        print("ВЕРДИКТ: Все строгие алгебраические инварианты Теоремы 5 УСПЕШНО СОБЛЮДЕНЫ!")
        print("   Математическое ядро библиотеки работает абсолютно корректно.")
    else:
        print("ВЕРДИКТ: Обнаружены математические расхождения с теорией:")
        for err in failures:
            print(f"   - {err}")
        print("="*80)
        assert False, " | ".join(failures)
    print("="*80 + "\n")

if __name__ == "__main__":
    test_theorem_5_invariants_degree_4()
