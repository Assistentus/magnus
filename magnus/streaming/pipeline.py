# -*- coding: utf-8 -*-
"""
magnus/streaming/pipeline.py
=============================
УНИВЕРСАЛЬНЫЙ потоковый процессор.

Принципы:
- НЕ знает про КАДВИ
- Работает с любыми данными через загрузчик
- Датчики передаются как параметр
- Формат данных передаётся как загрузчик
"""

import os
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Callable, Iterator, Any
from dataclasses import dataclass, field


# ================================================================
# РЕЗУЛЬТАТЫ
# ================================================================

@dataclass
class DayResult:
    """Результат обработки одного дня/файла."""
    source: str                # Идентификатор источника (дата, имя файла, ID)
    n_points: int
    rank_start: int
    rank_end: int
    delta_rank: int
    n_states_start: int
    n_states_end: int
    delta_states: int
    n_transitions_start: int
    n_transitions_end: int
    delta_transitions: int
    ranks_per_point: Optional[np.ndarray] = None
    rank_increases: Optional[np.ndarray] = None
    growth_times: List[int] = field(default_factory=list)


@dataclass
class ProcessingResult:
    """Результат обработки всего потока."""
    days: List[DayResult]
    total_points: int
    total_rank: int
    total_states: int
    total_transitions: int
    sensors_used: List[str]
    
    def to_dataframe(self) -> pd.DataFrame:
        """Преобразовать в DataFrame."""
        return pd.DataFrame([{
            'source': d.source,
            'n_points': d.n_points,
            'rank_start': d.rank_start,
            'rank_end': d.rank_end,
            'delta_rank': d.delta_rank,
            'n_states_start': d.n_states_start,
            'n_states_end': d.n_states_end,
            'delta_states': d.delta_states,
            'n_transitions_start': d.n_transitions_start,
            'n_transitions_end': d.n_transitions_end,
            'delta_transitions': d.delta_transitions,
        } for d in self.days])


# ================================================================
# УНИВЕРСАЛЬНЫЙ PIPELINE
# ================================================================

class StreamingPipeline:
    """
    Универсальный потоковый процессор Magnus.
    
    Не знает про конкретные системы. 
    Работает с любыми данными через загрузчик.
    
    Пример:
        # Загрузчик для произвольных данных
        def my_loader(filepath, sensors):
            df = pd.read_csv(filepath)
            return df[sensors].values
        
        pipeline = StreamingPipeline(
            sensors=['sensor1', 'sensor2'],
            loader=my_loader,
        )
        result = pipeline.process_files(filepaths)
    """
    
    def __init__(self,
                 sensors: List[str],
                 loader: Callable[[str, List[str]], Optional[np.ndarray]],
                 alpha: float = 0.05,
                 n_sigma: float = 1.5,
                 min_count: int = 2,
                 degree: int = 3,
                 p: int = 1_000_000_007):
        """
        Args:
            sensors: список датчиков (обязательно)
            loader: функция (filepath, sensors) → np.ndarray | None
            alpha: EMA коэффициент
            n_sigma: порог в сигмах
            min_count: минимум повторов
            degree: степень Magnus
            p: модуль Z_p
        """
        # Валидация
        if sensors is None:
            raise ValueError("Параметр 'sensors' обязателен")
        if not isinstance(sensors, (list, tuple)):
            raise ValueError(f"Должен быть список: {type(sensors).__name__}")
        if len(sensors) == 0:
            raise ValueError("Параметр 'sensors' пуст")
        for s in sensors:
            if not isinstance(s, str) or not s.strip():
                raise ValueError(f"Недопустимое имя датчика: {s!r}")
        
        if loader is None or not callable(loader):
            raise ValueError("Параметр 'loader' должен быть вызываемым")
        
        # Импорт Rust-класса
        from fr_rank_rs import StreamingMagnus
        
        self.requested_sensors = list(sensors)
        self.loader = loader
        self.alpha = alpha
        self.n_sigma = n_sigma
        self.min_count = min_count
        self.degree = degree
        self.p = p
        
        # Состояние
        self._proc_class = StreamingMagnus
        self.proc = None
        self.sensors_used = None
        self.n_sensors = None
        self.global_t = 0
        self.prev_rank = 0
        self.prev_states = 0
        self.prev_transitions = 0
    
    # ============================================================
    # ИНИЦИАЛИЗАЦИЯ ПРОЦЕССОРА
    # ============================================================
    
    def _init_processor(self, n_sensors: int):
        """Ленивая инициализация."""
        if self.proc is None:
            self.proc = self._proc_class(
                n_sensors=n_sensors,
                alpha=self.alpha,
                n_sigma=self.n_sigma,
                min_count=self.min_count,
                degree=self.degree,
            )
            self.n_sensors = n_sensors
    
    # ============================================================
    # ОБРАБОТКА ОДНОГО ФАЙЛА
    # ============================================================
    
    def process_day(self, filepath: str, source: str,
                     detail: bool = False) -> Optional[DayResult]:
        """
        Обрабатывает один файл.
        
        Args:
            filepath: путь к файлу
            source: идентификатор (дата, ID, имя)
            detail: сохранять ли ранг на каждой точке
        """
        # Загружаем данные через переданный loader
        data = self.loader(filepath, self.requested_sensors)
        
        if data is None:
            return None
        
        # Проверка размерности
        if data.ndim != 2:
            return None
        
        n_points, n_actual_sensors = data.shape
        
        if n_actual_sensors == 0:
            return None
        
        # Ленивая инициализация
        if self.proc is None:
            self._init_processor(n_actual_sensors)
            self.sensors_used = self.requested_sensors[:n_actual_sensors]
        elif n_actual_sensors != self.n_sensors:
            print(f"  ⚠️ {source}: другое число датчиков "
                  f"({n_actual_sensors} vs {self.n_sensors})")
            return None
        
        # C-contiguous для Rust
        data = np.ascontiguousarray(data, dtype=np.float64)
        flat = data.flatten()
        
        # Состояние до
        rank_start = self.prev_rank
        states_start = self.prev_states
        transitions_start = self.prev_transitions
        
        # Детали
        if detail:
            ranks_per_point = np.zeros(n_points, dtype=np.int64)
            rank_increases = np.zeros(n_points, dtype=np.int32)
        else:
            ranks_per_point = None
            rank_increases = None
        
        growth_times = []
        n_sensors = self.n_sensors
        
        # Поточечная обработка
        for i in range(n_points):
            start = i * n_sensors
            end = start + n_sensors
            point = flat[start:end]
            
            result = self.proc.process(point)
            self.global_t += 1
            
            if detail:
                ranks_per_point[i] = result['rank']
                rank_increases[i] = 1 if result['rank_increased'] else 0
            
            if result['rank_increased']:
                growth_times.append(i)
        
        # Финальные метрики
        rank_end = self.proc.get_rank()
        states_end = self.proc.get_n_states()
        transitions_end = self.proc.get_n_transitions()
        
        day_result = DayResult(
            source=source,
            n_points=n_points,
            rank_start=rank_start,
            rank_end=rank_end,
            delta_rank=rank_end - rank_start,
            n_states_start=states_start,
            n_states_end=states_end,
            delta_states=states_end - states_start,
            n_transitions_start=transitions_start,
            n_transitions_end=transitions_end,
            delta_transitions=transitions_end - transitions_start,
            ranks_per_point=ranks_per_point,
            rank_increases=rank_increases,
            growth_times=growth_times,
        )
        
        self.prev_rank = rank_end
        self.prev_states = states_end
        self.prev_transitions = transitions_end
        
        return day_result
    
    # ============================================================
    # ОБРАБОТКА ПОТОКА ФАЙЛОВ
    # ============================================================
    
    def process_files(self, filepaths: List[str],
                       sources: Optional[List[str]] = None,
                       detail_sources: Optional[List[str]] = None,
                       verbose: bool = True) -> ProcessingResult:
        """
        Обрабатывает список файлов.
        
        Args:
            filepaths: список путей
            sources: идентификаторы (если None — из имён файлов)
            detail_sources: для каких источников сохранять детали
            verbose: печатать прогресс
        """
        if sources is None:
            sources = [os.path.basename(fp).rsplit('.', 1)[0] 
                       for fp in filepaths]
        
        if detail_sources is None:
            detail_sources = []
        
        days = []
        
        if verbose:
            print(f"\n{'Источник':<20} {'Точек':>10} {'Δ Ранг':>8} "
                  f"{'Ранг':>10} {'Δ Сост':>8} {'Δ Перех':>10}")
            print("-"*75)
        
        for filepath, source in zip(filepaths, sources):
            detail = source in detail_sources
            result = self.process_day(filepath, source, detail=detail)
            
            if result is None:
                if verbose:
                    print(f"{source:<20} ПРОПУЩЕН")
                continue
            
            days.append(result)
            
            if verbose:
                print(f"{source:<20} {result.n_points:>10,} "
                      f"{result.delta_rank:>+8} {result.rank_end:>10} "
                      f"{result.delta_states:>+8} "
                      f"{result.delta_transitions:>+10}")
        
        return ProcessingResult(
            days=days,
            total_points=self.global_t,
            total_rank=self.proc.get_rank() if self.proc else 0,
            total_states=self.proc.get_n_states() if self.proc else 0,
            total_transitions=self.proc.get_n_transitions() if self.proc else 0,
            sensors_used=self.sensors_used or [],
        )
    
    # ============================================================
    # ОБРАБОТКА ПОТОКА ТОЧЕК
    # ============================================================
    
    def process_stream(self, stream: Iterator[Dict[str, Any]],
                        source_key: str = 'source',
                        values_key: str = 'values') -> ProcessingResult:
        """
        Обрабатывает поток точек.
        
        Args:
            stream: итератор словарей вида {'source': str, 'values': np.ndarray}
            source_key: ключ для идентификатора
            values_key: ключ для значений
        """
        days_data = {}
        current_source = None
        current_day_results = []
        
        for item in stream:
            source = item[source_key]
            values = np.ascontiguousarray(item[values_key], dtype=np.float64)
            
            if current_source != source:
                # Закрываем предыдущий
                if current_source is not None and current_day_results:
                    days_data[current_source] = self._finalize_stream_day(
                        current_source, current_day_results
                    )
                current_source = source
                current_day_results = []
            
            result = self.proc.process(values) if self.proc else None
            self.global_t += 1
            current_day_results.append(result)
        
        # Закрываем последний
        if current_source is not None and current_day_results:
            days_data[current_source] = self._finalize_stream_day(
                current_source, current_day_results
            )
        
        return ProcessingResult(
            days=list(days_data.values()),
            total_points=self.global_t,
            total_rank=self.proc.get_rank() if self.proc else 0,
            total_states=self.proc.get_n_states() if self.proc else 0,
            total_transitions=self.proc.get_n_transitions() if self.proc else 0,
            sensors_used=self.sensors_used or [],
        )
    
    def _finalize_stream_day(self, source: str, results: List[Dict]) -> DayResult:
        """Собирает DayResult из потока."""
        valid = [r for r in results if r is not None]
        
        if not valid:
            return DayResult(
                source=source, n_points=0,
                rank_start=0, rank_end=0, delta_rank=0,
                n_states_start=0, n_states_end=0, delta_states=0,
                n_transitions_start=0, n_transitions_end=0, delta_transitions=0,
            )
        
        return DayResult(
            source=source,
            n_points=len(valid),
            rank_start=valid[0]['rank'],
            rank_end=valid[-1]['rank'],
            delta_rank=valid[-1]['rank'] - valid[0]['rank'],
            n_states_start=valid[0]['n_states'],
            n_states_end=valid[-1]['n_states'],
            delta_states=valid[-1]['n_states'] - valid[0]['n_states'],
            n_transitions_start=valid[0]['n_transitions'],
            n_transitions_end=valid[-1]['n_transitions'],
            delta_transitions=valid[-1]['n_transitions'] - valid[0]['n_transitions'],
        )
    
    # ============================================================
    # СБРОС
    # ============================================================
    
    def reset(self):
        """Сброс процессора."""
        if self.proc:
            self.proc.reset()
        self.global_t = 0
        self.prev_rank = 0
        self.prev_states = 0
        self.prev_transitions = 0
