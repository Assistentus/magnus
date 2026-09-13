# -*- coding: utf-8 -*-
"""
magnus/streaming/formats/npy_concatenated.py
==============================================
Загрузчик для ОДНОГО объединённого .npy файла с метаданными.

Особенности:
- Memory-mapped загрузка (мгновенная)
- Резолвление source по абсолютной позиции t
- Совместим с обычным loader-интерфейсом
- НЕ требует аннотации окон: source определяется через source_at(t)
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any


class NPYConcatenatedLoader:
    """
    Загружает данные из объединённого .npy файла с метаданными.

    Файловая структура:
        data_dir/
        ├── combined.npy         (n_points, n_sensors) float64
        └── combined.meta.json   метаданные + file_boundaries

    Использование:
        loader = NPYConcatenatedLoader('/path/to/data_dir')
        data = loader.get_slice(0, 10000)     # срез точек
        source = loader.source_at(5_500_000)   # определение источника
    """

    def __init__(self, data_dir: str, use_mmap: bool = True):
        self.data_dir = Path(data_dir)
        self.use_mmap = use_mmap

        self.npy_path = self.data_dir / 'combined.npy'
        self.meta_path = self.data_dir / 'combined.meta.json'

        if not self.npy_path.exists():
            raise FileNotFoundError(f"Не найден: {self.npy_path}")
        if not self.meta_path.exists():
            raise FileNotFoundError(f"Не найден: {self.meta_path}")

        # Метаданные
        with open(self.meta_path, 'r', encoding='utf-8') as f:
            self.meta = json.load(f)

        # Данные (mmap или реальный массив)
        if use_mmap:
            self.data = np.load(self.npy_path, mmap_mode='r')
        else:
            self.data = np.load(self.npy_path)

        self.file_boundaries = self.meta['file_boundaries']
        self.sensors = self.meta['sensors']
        self.n_points = self.meta['n_points']
        self.n_sensors = self.meta['n_sensors']

    def __call__(self, filepath: str, sensors: List[str]) -> Optional[np.ndarray]:
        """
        Совместим с обычным loader-интерфейсом.

        filepath может быть:
        - именем source ('20260206')
        - путём к оригинальному CSV ('.../20260206.csv')
        """
        source = Path(filepath).stem

        for b in self.file_boundaries:
            if b['source'] == source:
                return self.data[b['start']:b['end']]

        return None

    def get_slice(self, start: int, end: int) -> np.ndarray:
        """Получить срез данных по позициям."""
        return self.data[start:end]

    def get_all(self) -> np.ndarray:
        """Весь массив (mmap-view)."""
        return self.data

    def flat_view(self) -> np.ndarray:
        """Плоский view (для передачи в Rust)."""
        return self.data.reshape(-1)

    def source_at(self, t: int) -> Optional[str]:
        """
        Определить source по абсолютной позиции t.

        Использует бинарный поиск по границам.
        """
        # Бинарный поиск
        lo, hi = 0, len(self.file_boundaries) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            b = self.file_boundaries[mid]
            if t < b['start']:
                hi = mid - 1
            elif t >= b['end']:
                lo = mid + 1
            else:
                return b['source']
        return None

    def source_range(self, start: int, end: int) -> List[str]:
        """
        Определить все sources в диапазоне [start, end).

        Возвращает список в порядке следования.
        """
        sources = []
        for b in self.file_boundaries:
            if b['end'] <= start:
                continue
            if b['start'] >= end:
                break
            sources.append(b['source'])
        return sources

    def all_sources(self) -> List[str]:
        """Список всех источников в порядке следования."""
        return [b['source'] for b in self.file_boundaries]

    def boundaries(self):
        """Возвращает boundaries как список кортежей (start, end, source)."""
        return [
            (b['start'], b['end'], b['source'])
            for b in self.file_boundaries
        ]

    def __repr__(self) -> str:
        return (
            f"NPYConcatenatedLoader("
            f"n_points={self.n_points:,}, "
            f"n_sensors={self.n_sensors}, "
            f"n_files={len(self.file_boundaries)}, "
            f"mmap={self.use_mmap})"
        )
