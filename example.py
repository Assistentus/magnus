#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

# Автоматически находим корень проекта и добавляем его в пути поиска Python.
# Это делает запуск скрипта абсолютно независимым от того, из какой папки его запускают.
sys.path.append(str(Path(__file__).resolve().parent))

# Импортируем из нового пакета magnus
from magnus import TextPresentation, MagnusAlgebra, FRCodeRegistry, HomologySolver

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🛸 MAGNUS: ПРИМЕР СТРУКТУРНОГО ГОМОЛОГИЧЕСКОГО АНАЛИЗА ТЕКСТА")
    print("="*80)

    # 1. Тестовый текст (короткий сюжетный набросок, продублированный для объема)
    base_text = "Он вошел в комнату. Он не знал, что делать. В комнате было темно. " \
                "Что он будет делать дальше? Он сел на стул. Стул был старый. " \
                "В старом стуле была тайна. Тайна не давала ему спать. " \
                "Он не мог спать. Он думал о тайне. Тайна была в комнате."
    text = base_text * 10  # Получаем около 110 предложений для наглядности

    # 2. Создаем копредставление группы. 
    # ВНИМАНИЕ: Здесь автоматически сработает наш алгоритм "Homological Feature Selection",
    # который отберет 20 самых сильных синтаксических узлов вместо простой частотной выборки.
    pres = TextPresentation(text, k_vocab=20, max_relations=1000)
    print(f"   [+] Отношения R построены. Найдено нетривиальных предложений: {len(pres.relations)}")

    # 3. Инициализируем алгебру Магнуса степени 4 (требование для H3-кодов)
    magnus = MagnusAlgebra(K=pres.k_vocab, degree=4)
    print(f"   [+] Базис Магнуса инициализирован. Размерность пространства f: {magnus.dim}")

    # 4. Переводим отношения (предложения) в многочлены идеала r
    r_generators = [magnus.expand_word(rel) for rel in pres.relations]

    # 5. Строим матрицу конкретного fr-кода: rr + frf + rff (Инвариант H2, Теорема 5)
    print("\n--- СБОРКА И РАСЧЕТ ИНВАРИАНТА H2 (rr + frf + rff) ---")
    c_matrix = FRCodeRegistry.build_rr_frf_rff(magnus, r_generators)
    print(f"   [+] Матрица c1 построена: {c_matrix.shape[0]} строк на {c_matrix.shape[1]} столбцов")

    # 6. Вычисляем ранг и свободный гомологический остаток (фактор-пространство)
    # Если в системе установлен Rust-модуль, расчет пройдет мгновенно. 
    # Если нет — прозрачно отработает чистый Python-алгоритм.
    solver = HomologySolver(p=10**9 + 7)
    results = solver.evaluate(c_matrix, dim_f=magnus.dim)

    print("\n📊 РЕЗУЛЬТАТЫ:")
    print(f"   * Исходная размерность пространства f: {results['dim_f']}")
    print(f"   * Вычисленный ранг матрицы кода c1:    {results['rank_c']}")
    print(f"   * Размерность фактора f/c1:            {results['dim_factor']} (Математически строго >= K={pres.k_vocab})")
    print(f"   * Нуль-пространство (Nullity):         {results['nullity']}")
    print("="*80 + "\n")
