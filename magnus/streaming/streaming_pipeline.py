# -*- coding: utf-8 -*-
"""
magnus/streaming/streaming_pipeline.py
========================================
МОДУЛЬ потоковой обработки данных.
"""

import os
import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class DayResult:
    date: str
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
    days: List[DayResult]
    total_points: int
    total_rank: int
    total_states: int
    total_transitions: int
    sensors_used: List[str]
    
    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([{
            'date': d.date,
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


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().replace('\t', ' ') for c in df.columns]
    return df


def detect_available_sensors(filepath: str, requested: List[str]) -> List[str]:
    try:
        df = pd.read_csv(filepath, sep=';', decimal=',', nrows=5)
        df = normalize_columns(df)
        return [s for s in requested if s in df.columns]
    except Exception:
        return []


def load_day(filepath: str, sensors: List[str]) -> Optional[np.ndarray]:
    try:
        df = pd.read_csv(filepath, sep=';', decimal=',')
        df = normalize_columns(df)
        available = [s for s in sensors if s in df.columns]
        if not available:
            return None
        return np.ascontiguousarray(df[available].values, dtype=np.float64)
    except Exception as e:
        print(f"  ⚠️ Ошибка загрузки {filepath}: {e}")
        return None


class StreamingPipeline:
    def __init__(self, sensors: List[str],
                 alpha: float = 0.05, n_sigma: float = 1.5,
                 min_count: int = 2, degree: int = 3):
        if sensors is None:
            raise ValueError("Параметр 'sensors' обязателен")
        if not isinstance(sensors, (list, tuple)):
            raise ValueError(f"Должен быть список, получено: {type(sensors).__name__}")
        if len(sensors) == 0:
            raise ValueError("Параметр 'sensors' пуст")
        for s in sensors:
            if not isinstance(s, str) or not s.strip():
                raise ValueError(f"Недопустимое имя датчика: {s!r}")
        
        from fr_rank_rs import StreamingMagnus
        
        self.requested_sensors = list(sensors)
        self.sensors_used = None
        self.n_sensors = None
        self.proc = None
        self.alpha = alpha
        self.n_sigma = n_sigma
        self.min_count = min_count
        self.degree = degree
        self.global_t = 0
        self.prev_rank = 0
        self.prev_states = 0
        self.prev_transitions = 0
        self._proc_class = StreamingMagnus
    
    def _init_processor(self, n_sensors: int):
        if self.proc is None:
            self.proc = self._proc_class(
                n_sensors=n_sensors,
                alpha=self.alpha,
                n_sigma=self.n_sigma,
                min_count=self.min_count,
                degree=self.degree,
            )
            self.n_sensors = n_sensors
    
    def process_day(self, filepath: str, date: str,
                     detail: bool = False) -> Optional[DayResult]:
        available = detect_available_sensors(filepath, self.requested_sensors)
        if not available:
            print(f"  ⚠️ {date}: ни один датчик не найден")
            return None
        
        if self.proc is None:
            self._init_processor(len(available))
            self.sensors_used = available
            if len(available) != len(self.requested_sensors):
                missing = set(self.requested_sensors) - set(available)
                print(f"  ⚠️ Отсутствуют: {missing}")
        elif len(available) != self.n_sensors:
            print(f"  ⚠️ {date}: другое число датчиков")
            return None
        
        data = load_day(filepath, self.sensors_used)
        if data is None:
            return None
        
        n_points = len(data)
        flat = data.flatten()
        
        rank_start = self.prev_rank
        states_start = self.prev_states
        transitions_start = self.prev_transitions
        
        if detail:
            ranks_per_point = np.zeros(n_points, dtype=np.int64)
            rank_increases = np.zeros(n_points, dtype=np.int32)
        else:
            ranks_per_point = None
            rank_increases = None
        
        growth_times = []
        n_sensors = self.n_sensors
        
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
        
        rank_end = self.proc.get_rank()
        states_end = self.proc.get_n_states()
        transitions_end = self.proc.get_n_transitions()
        
        day_result = DayResult(
            date=date, n_points=n_points,
            rank_start=rank_start, rank_end=rank_end,
            delta_rank=rank_end - rank_start,
            n_states_start=states_start, n_states_end=states_end,
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
    
    def process_files(self, filepaths, dates=None, detail_days=None, verbose=True):
        if dates is None:
            dates = [os.path.basename(fp).replace('.csv', '') for fp in filepaths]
        if detail_days is None:
            detail_days = []
        
        days = []
        if verbose:
            print(f"\n{'Дата':<12} {'Точек':>8} {'Δ Ранг':>8} "
                  f"{'Ранг':>8} {'Δ Сост':>8} {'Δ Перех':>10}")
            print("-"*70)
        
        for filepath, date in zip(filepaths, dates):
            detail = date in detail_days
            result = self.process_day(filepath, date, detail=detail)
            if result is None:
                if verbose:
                    print(f"{date:<12} ПРОПУЩЕН")
                continue
            days.append(result)
            if verbose:
                print(f"{date:<12} {result.n_points:>8,} "
                      f"{result.delta_rank:>+8} {result.rank_end:>8} "
                      f"{result.delta_states:>+8} {result.delta_transitions:>+10}")
        
        return ProcessingResult(
            days=days,
            total_points=self.global_t,
            total_rank=self.proc.get_rank() if self.proc else 0,
            total_states=self.proc.get_n_states() if self.proc else 0,
            total_transitions=self.proc.get_n_transitions() if self.proc else 0,
            sensors_used=self.sensors_used or [],
        )
    
    def reset(self):
        if self.proc:
            self.proc.reset()
        self.global_t = 0
        self.prev_rank = 0
        self.prev_states = 0
        self.prev_transitions = 0
