# -*- coding: utf-8 -*-
"""
magnus/streaming/predictor.py
==============================
Predictor: автоматическое предсказание аномалий.

Трёхуровневая система:
1. FAST (за 1-6 часов) — острые аварии
2. SLOW (за 5-13 дней) — деградация

Конфигурация задаётся через YAML или PredictorConfig.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
import json

from .predictor_config import (
    PredictorConfig,
    load_predictor_config,
    load_config_from_dict,
    Rule,
)


# ================================================================
# РЕЗУЛЬТАТЫ
# ================================================================

@dataclass
class Alert:
    """Один алерт."""
    t: int
    source: Optional[str]
    level: str           # 'FAST' | 'SLOW'
    score: int
    signals: List[str]
    urgency: str         # 'critical' | 'high' | 'medium' | 'low'

    def as_dict(self) -> Dict[str, Any]:
        return {
            't': self.t,
            'source': self.source,
            'level': self.level,
            'score': self.score,
            'signals': self.signals,
            'urgency': self.urgency,
        }


@dataclass
class PredictionResult:
    """Результат работы Predictor."""
    alerts: List[Alert]
    n_fast: int = 0
    n_slow: int = 0
    files_with_alerts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    config_name: str = "default"

    def as_dict(self) -> Dict[str, Any]:
        return {
            'config_name': self.config_name,
            'alerts': [a.as_dict() for a in self.alerts],
            'n_fast': self.n_fast,
            'n_slow': self.n_slow,
            'files_with_alerts': self.files_with_alerts,
        }

    def to_json(self, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.as_dict(), f, ensure_ascii=False, indent=2)
        print(f'💾 Алерты: {path}')

    def summary(self) -> str:
        lines = [
            f'Конфиг:         {self.config_name}',
            f'Алертов всего:  {len(self.alerts)}',
            f'  FAST:         {self.n_fast}',
            f'  SLOW:         {self.n_slow}',
            f'Файлов с алертами: {len(self.files_with_alerts)}',
        ]
        return '\n'.join(lines)

    def print_alerts(self):
        print()
        print('=' * 100)
        print('ВСЕ АЛЕРТЫ')
        print('=' * 100)
        print(f'{"t":>10} {"Источник":<12} {"Уровень":<8} {"Score":>6} {"Urgency":<10} {"Сигналы":<40}')
        print('-' * 100)
        for a in self.alerts:
            signals_str = ', '.join(a.signals[:3])
            print(f'{a.t:>10} {a.source or "?":<12} {a.level:<8} '
                  f'{a.score:>6} {a.urgency:<10} {signals_str:<40}')


# ================================================================
# PREDICTOR
# ================================================================

class AnomalyPredictor:
    """
    Predictor аномалий (FAST + SLOW).

    Использование:
        # 1. Из YAML
        predictor = AnomalyPredictor.from_config('config.yaml',
                                                   sensors=loader.sensors)

        # 2. Из конфига программно
        config = PredictorConfig(...)
        predictor = AnomalyPredictor(sensors=loader.sensors, config=config)

        # 3. Запуск
        result = predictor.predict(loader)
        result.print_alerts()
    """

    def __init__(self,
                 sensors: List[str],
                 config: Optional[PredictorConfig] = None):
        """
        Args:
            sensors: список имён датчиков (из данных)
            config: PredictorConfig (если None — пустой с auto)
        """
        if not sensors:
            raise ValueError("sensors не может быть пустым")

        self.sensors = sensors
        self.n_sensors = len(sensors)
        self.config = config or PredictorConfig()

        # Индекс датчиков
        self.sensor_idx = {s: i for i, s in enumerate(sensors)}

        # Валидация
        warnings = self.config.validate_for_sensors(sensors)
        if warnings:
            print("⚠️  ПРЕДУПРЕЖДЕНИЯ КОНФИГА:")
            for w in warnings:
                print(f"   {w}")
            print()

    # ============================================================
    # КОНСТРУКТОРЫ
    # ============================================================

    @classmethod
    def from_config(cls,
                     config_path: str,
                     sensors: List[str]) -> 'AnomalyPredictor':
        """Создаёт Predictor из YAML-конфига."""
        config = load_predictor_config(config_path)
        return cls(sensors=sensors, config=config)

    @classmethod
    def from_dict(cls,
                   config_dict: Dict,
                   sensors: List[str]) -> 'AnomalyPredictor':
        """Создаёт Predictor из словаря."""
        config = load_config_from_dict(config_dict)
        return cls(sensors=sensors, config=config)

    # ============================================================
    # ВНУТРЕННИЕ
    # ============================================================

    def _compute_score(self,
                        rules: List[Rule],
                        baseline: np.ndarray,
                        current: np.ndarray) -> tuple:
        """
        Считает score по правилам.

        Returns:
            (total_score, signals) — score и список сигналов
        """
        total_score = 0
        signals = []

        for rule in rules:
            # Находим датчики, подходящие под правило
            matched_sensors = [
                s for s in self.sensors if rule.matches_sensor(s)
            ]

            for sensor_name in matched_sensors:
                idx = self.sensor_idx[sensor_name]

                if baseline[idx] < 1e-6:
                    continue

                d = (current[idx] - baseline[idx]) / abs(baseline[idx])

                matched = (
                    (rule.direction == 'up' and d > rule.threshold) or
                    (rule.direction == 'down' and d < -rule.threshold) or
                    (rule.direction == 'any' and abs(d) > rule.threshold)
                )

                if matched:
                    total_score += rule.weight
                    signals.append(f'{sensor_name}({d*100:+.1f}%)')

        return total_score, signals

    # ============================================================
    # FAST
    # ============================================================

    def _detect_fast(self, data: np.ndarray, loader) -> List[Alert]:
        """FAST-детекция (переходы норма→аномалия)."""
        cfg = self.config
        fast = cfg.fast

        if not fast.enabled or not fast.rules:
            return []

        hour = cfg.points_per_hour
        warmup_pts = cfg.warmup_hours * hour
        baseline_pts = fast.baseline_hours * hour
        window_pts = fast.window_hours * hour

        alerts = []
        in_alert = False

        start_i = max(baseline_pts, warmup_pts)

        for i in range(start_i, data.shape[0] - hour, hour):
            seg_baseline = data[i - baseline_pts:i]
            seg_current = data[i:i + window_pts]

            if seg_baseline.shape[0] < 100:
                continue

            baseline = seg_baseline.mean(axis=0)
            current = seg_current.mean(axis=0)

            score, signals = self._compute_score(
                fast.rules, baseline, current
            )

            if score >= fast.min_score:
                if not in_alert:
                    urgency = cfg.urgency.classify(score)
                    alerts.append(Alert(
                        t=i,
                        source=loader.source_at(i),
                        level='FAST',
                        score=score,
                        signals=signals,
                        urgency=urgency,
                    ))
                    in_alert = True
            else:
                in_alert = False

        return alerts

    # ============================================================
    # SLOW
    # ============================================================

    def _detect_slow(self, data: np.ndarray, loader) -> List[Alert]:
        """SLOW-детекция (деградация)."""
        cfg = self.config
        slow = cfg.slow

        if not slow.enabled or not slow.rules:
            return []

        day = 24 * cfg.points_per_hour
        window_pts = slow.window_days * day
        warmup_pts = cfg.warmup_hours * cfg.points_per_hour

        alerts = []

        for b in loader.file_boundaries:
            mid = (b['start'] + b['end']) // 2
            t_past = mid - window_pts

            if t_past < warmup_pts:
                continue

            seg_now = data[mid:mid + cfg.points_per_hour]
            seg_past = data[t_past:t_past + cfg.points_per_hour]

            if seg_past.shape[0] < 100 or seg_now.shape[0] < 100:
                continue

            baseline = seg_past.mean(axis=0)
            current = seg_now.mean(axis=0)

            score, signals = self._compute_score(
                slow.rules, baseline, current
            )

            if score >= slow.min_score:
                urgency = cfg.urgency.classify(score)
                alerts.append(Alert(
                    t=mid,
                    source=b['source'],
                    level='SLOW',
                    score=score,
                    signals=signals,
                    urgency=urgency,
                ))

        return alerts

    # ============================================================
    # PUBLIC API
    # ============================================================

    def predict(self, loader) -> PredictionResult:
        """Запускает всю систему предсказания."""
        data = loader.get_all()

        fast_alerts = self._detect_fast(data, loader)
        slow_alerts = self._detect_slow(data, loader)

        all_alerts = sorted(fast_alerts + slow_alerts, key=lambda a: a.t)

        # Сводка по файлам
        files_with_alerts: Dict[str, Dict[str, int]] = {}
        for a in all_alerts:
            if a.source is None:
                continue
            if a.source not in files_with_alerts:
                files_with_alerts[a.source] = {'FAST': 0, 'SLOW': 0}
            files_with_alerts[a.source][a.level] = \
                files_with_alerts[a.source].get(a.level, 0) + 1

        return PredictionResult(
            alerts=all_alerts,
            n_fast=len(fast_alerts),
            n_slow=len(slow_alerts),
            files_with_alerts=files_with_alerts,
            config_name=self.config.name,
        )
