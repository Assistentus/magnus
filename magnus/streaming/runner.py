# -*- coding: utf-8 -*-
"""
magnus/streaming/runner.py
============================
Универсальный запуск обработки.

Поддерживает два режима:
- sequential: файлы обрабатываются по одному (старый режим)
- concatenated: все файлы как единый поток (новый режим)
"""

import os
from glob import glob
from typing import List, Optional, Dict, Any
from pathlib import Path

import numpy as np

from .pipeline import StreamingPipeline, ProcessingResult
from .formats import AutoDetectLoader
from .config_schema import MagnusConfig, SourceConfig


def create_loader(format_type: str = 'auto', **kwargs):
    if callable(format_type):
        return format_type
    if format_type in ('auto', 'csv', 'tsv'):
        return AutoDetectLoader(
            normalize_columns=True,
            skip_missing=True,
            verbose=kwargs.get('verbose', False),
        )
    if format_type == 'parquet':
        try:
            from .formats import ParquetLoader
            return ParquetLoader()
        except ImportError:
            raise ImportError("ParquetLoader не найден. pip install pyarrow")
    if format_type == 'excel':
        try:
            from .formats import ExcelLoader
            return ExcelLoader()
        except ImportError:
            raise ImportError("ExcelLoader не найден. pip install openpyxl")
    raise ValueError(
        f"Формат '{format_type}' не поддерживается. "
        f"Допустимые: auto, csv, tsv, parquet, excel, callable"
    )


class UniversalRunner:
    """
    Универсальный runner по конфигу MagnusConfig.
    """

    def __init__(self, config: MagnusConfig):
        if config is None:
            raise ValueError("config не может быть None")
        self.config = config
        self._loader = None

    def find_files(self) -> List[str]:
        all_files = []
        for src in self.config.sources:
            path = Path(src.path)
            if path.is_file():
                all_files.append(str(path))
            elif path.is_dir():
                pattern = os.path.join(str(path), src.pattern)
                files = sorted(glob(pattern))
                all_files.extend(files)
            else:
                print(f"⚠️ Путь не существует: {path}")
        return sorted(set(all_files))

    def get_source_key(self, filepath: str) -> str:
        return Path(filepath).stem

    def _create_pipeline(self, sensors: List[str]) -> StreamingPipeline:
        if self.config.sources:
            format_type = self.config.sources[0].format
        else:
            format_type = 'auto'

        loader = create_loader(format_type)
        proc = self.config.processor

        pipeline = StreamingPipeline(
            sensors=sensors,
            loader=loader,
            alpha=proc.alpha,
            n_sigma=proc.n_sigma,
            min_count=proc.min_count,
            degree=proc.degree,
            path_length=proc.path_length,
            window_size=proc.window_size,
            overlap=proc.overlap,
        )
        return pipeline

    def run(self,
            sensor_set_name: str = 'default',
            mode: str = 'concatenated',
            verbose: bool = True,
            detail_sources: Optional[List[str]] = None) -> Optional[ProcessingResult]:
        """
        Запускает обработку.

        Args:
            sensor_set_name: имя набора датчиков
            mode: 'sequential' (по одному файлу)
                  'concatenated' (все файлы как единый поток)
            verbose: печатать прогресс
            detail_sources: для sequential — какие источники сохранять с деталями

        Returns:
            ProcessingResult или None
        """
        if mode not in ('sequential', 'concatenated'):
            print(f"❌ Неверный режим '{mode}'. "
                  f"Допустимые: sequential, concatenated")
            return None

        try:
            sensor_set = self.config.get_sensor_set(sensor_set_name)
        except ValueError as e:
            print(f"❌ {e}")
            return None

        sensors = sensor_set.columns

        if verbose:
            print(f"📂 Конфиг: {self.config.name}")
            print(f"📂 Набор датчиков: {sensor_set_name} ({len(sensors)} шт.)")
            for s in sensors:
                print(f"   - {s}")
            print(f"📂 Режим: {mode}")
            print()

        files = self.find_files()
        if not files:
            print(f"❌ Файлы не найдены")
            return None

        if verbose:
            print(f"📂 Найдено {len(files)} файлов\n")

        pipeline = self._create_pipeline(sensors)
        sources = [self.get_source_key(f) for f in files]

        if mode == 'concatenated':
            result = pipeline.process_concatenated(
                files, sources,
                verbose=verbose,
            )
        else:
            if detail_sources is None:
                detail_sources = []
            result = pipeline.process_files(
                files, sources,
                detail_sources=detail_sources,
                verbose=verbose,
            )

        if verbose:
            print(f"\n{'='*80}")
            print(f"ИТОГИ:")
            print(f"  Конфиг:           {self.config.name}")
            print(f"  Набор:            {sensor_set_name}")
            print(f"  Режим:            {mode}")
            print(f"  Датчиков:         {len(result.sensors_used)}")
            print(f"  Точек:            {result.total_points:,}")
            print(f"  Финальный ранг:   {result.total_rank:,}")
            print(f"  Состояний:        {result.total_states:,}")
            print(f"  Переходов:        {result.total_transitions:,}")
            print(f"  Слов (путей):     {result.total_words:,}")
            print(f"  degree:           {result.degree}")
            print(f"  path_length:      {result.path_length}")
            if result.window_size > 0:
                print(f"  window_size:      {result.window_size}")
                if result.overlap > 0:
                    pct = 100 * result.overlap // result.window_size
                    print(f"  overlap:          {result.overlap} ({pct}%)")
                print(f"  Окон закрыто:     {len(result.window_fingerprints)}")

        return result

    def list_sensor_sets(self) -> List[str]:
        return self.config.list_sensor_sets()

    def list_sources(self) -> List[str]:
        return self.config.list_sources()

    def info(self) -> str:
        return self.config.info()

    def describe(self) -> Dict[str, Any]:
        return {
            'config_name': self.config.name,
            'config_path': self.config.config_path,
            'sources': self.config.list_sources(),
            'sensor_sets': self.config.list_sensor_sets(),
            'processor': self.config.processor.as_dict(),
            'n_files': len(self.find_files()),
        }