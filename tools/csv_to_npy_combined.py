# -*- coding: utf-8 -*-
"""
tools/csv_to_npy_combined.py
=============================
Конвертер всех CSV файлов в ОДИН объединённый .npy + метаданные.

Использование:
    python tools/csv_to_npy_combined.py
"""

import os
import sys
import json
import time
import datetime
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List


def convert_csv_dir_to_combined_npy(
    csv_dir: str,
    output_dir: str,
    sensors: List[str],
    pattern: str = "*.csv",
    verbose: bool = True,
):
    """
    Конвертирует все CSV из директории в ОДИН combined.npy + метаданные.
    """
    csv_dir = Path(csv_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(csv_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(
            f"Нет файлов по паттерну {pattern} в {csv_dir}"
        )

    if verbose:
        print(f"Найдено файлов: {len(files)}")
        print()

    # 1. Загружаем все в список
    all_arrays = []
    boundaries = []
    total_points = 0

    t_start = time.time()

    for i, csv_path in enumerate(files, 1):
        name = csv_path.stem

        if verbose:
            print(f"  [{i:>2}/{len(files)}] {name}...", end=' ')
            sys.stdout.flush()

        # Читаем CSV
        try:
            df = pd.read_csv(csv_path, sep=';', decimal=',')
        except Exception as e:
            print(f"ОШИБКА: {e}")
            continue

        df.columns = [c.strip().replace('\t', ' ') for c in df.columns]

        # Проверка датчиков
        missing = [s for s in sensors if s not in df.columns]
        if missing:
            print(f"⚠️ отсутствуют {missing}")
            continue

        # Извлекаем
        data = df[sensors].values.astype(np.float64)
        data = np.ascontiguousarray(data)
        n_pts = data.shape[0]

        all_arrays.append(data)
        boundaries.append({
            'source': name,
            'start': total_points,
            'end': total_points + n_pts,
            'n_points': n_pts,
        })
        total_points += n_pts

        if verbose:
            print(f"{n_pts:>8,} точек")

    t_load = time.time() - t_start

    if verbose:
        print()
        print(f"Загрузка CSV: {t_load:.1f}s")

    # 2. Объединяем
    if verbose:
        print(f"Объединение {len(all_arrays)} массивов...")

    t_start = time.time()
    combined = np.vstack(all_arrays)
    combined = np.ascontiguousarray(combined)
    t_vstack = time.time() - t_start

    if verbose:
        print(f"Объединение: {t_vstack:.1f}s")
        print(f"Итог: {combined.shape} "
              f"({combined.nbytes / 1024 / 1024:.1f} MB)")

    # 3. Сохраняем NPY
    npy_path = output_dir / 'combined.npy'
    t_start = time.time()
    np.save(npy_path, combined)
    t_save = time.time() - t_start

    if verbose:
        print(f"💾 NPY сохранён: {npy_path} ({t_save:.1f}s)")

    # 4. Сохраняем метаданные
    meta = {
        'n_points': int(combined.shape[0]),
        'n_sensors': int(combined.shape[1]),
        'sensors': sensors,
        'dtype': 'float64',
        'file_boundaries': boundaries,
        'source_csv_dir': str(csv_dir),
        'created_at': datetime.datetime.now().isoformat(),
    }

    meta_path = output_dir / 'combined.meta.json'
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"💾 Метаданные: {meta_path}")
        print()
        print("=" * 60)
        print("ГОТОВО!")
        print("=" * 60)
        print(f"  Файлов:   {len(boundaries)}")
        print(f"  Точек:    {combined.shape[0]:,}")
        print(f"  Датчиков: {combined.shape[1]}")
        print(f"  Размер:   {combined.nbytes / 1024 / 1024:.1f} MB")
        print(f"  Общее время: {t_load + t_vstack + t_save:.1f}s")

    return npy_path, meta_path


if __name__ == "__main__":
    sensors = ['N tk','Qk/g','Pm v/vh','Pgaza na vihod',
               'P gaza na vhode d dozator','V red','V gen','V sau',
               't gaz na vih iz GTD','t masla na vihode iz GTD',
               't vozd na vh v GTD','Ugol HD']

    convert_csv_dir_to_combined_npy(
        csv_dir='/home/m/Документы/лобачевский/турбо/KADVI/КАДВИ/КАДВИ/007',
        output_dir='/home/m/Q/magnus/data/kadvi_007_npy',
        sensors=sensors,
    )
