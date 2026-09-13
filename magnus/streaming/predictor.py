# -*- coding: utf-8 -*-
"""
magnus/streaming/predictor.py
==============================
Predictor: автоматическое предсказание аномалий.

Двухуровневая система:
1. FAST (за 1-6 часов) — острые аварии
2. SLOW (за 5-13 дней) — деградация

Конфигурация задаётся через YAML или PredictorConfig.

Универсальный — не знает про конкретные установки.

Пример YAML-конфига:
    predictor:
      name: "My Installation"
      
      fast:
        window_hours: 6
        baseline_hours: 24
        min_score: 5
        rules:
          - sensor: "sensor1"
            threshold: 0.05
            direction: "up"
            weight: 3
      
      slow:
        window_days: 10
        min_score: 4
        rules:
          - sensor: "sensor1"
            threshold: 0.15
            direction: "up"
            weight: 3
      
      urgency:
        critical_score: 7
        high_score: 5
        medium_score: 3
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
import json
import re
import yaml


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
        print(f'{"t":>10} {"Источник":<12} {"Уровень":<8} {"Score":>6} '
              f'{"Urgency":<10} {"Сигналы":<40}')
        print('-' * 100)
        for a in self.alerts:
            signals_str = ', '.join(a.signals[:3])
            print(f'{a.t:>10} {a.source or "?":<12} {a.level:<8} '
                  f'{a.score:>6} {a.urgency:<10} {signals_str:<40}')


# ================================================================
# ПРАВИЛА
# ================================================================

@dataclass
class Rule:
    """
    Одно правило детекции.

    Attributes:
        sensor: имя датчика (точное) или regex-паттерн
        threshold: порог (0.05 = 5%)
        direction: 'up' | 'down' | 'any'
        weight: вес при подсчёте score (1-10)
    """
    sensor: str
    threshold: float
    direction: str = 'any'
    weight: int = 1

    def __post_init__(self):
        if not self.sensor:
            raise ValueError("Rule.sensor не может быть пустым")
        if self.threshold <= 0:
            raise ValueError(f"threshold={self.threshold} должен быть > 0")
        if self.direction not in ('up', 'down', 'any'):
            raise ValueError(
                f"direction='{self.direction}' не поддерживается. "
                f"Допустимые: up, down, any"
            )
        if not (1 <= self.weight <= 10):
            raise ValueError(f"weight={self.weight} должен быть в [1, 10]")

    def matches_sensor(self, sensor_name: str) -> bool:
        """Проверяет, подходит ли датчик под правило."""
        if self.sensor == sensor_name:
            return True
        # Regex если есть спецсимволы
        if any(c in self.sensor for c in '.*+?[]()|^$'):
            try:
                return bool(re.match(self.sensor, sensor_name))
            except re.error:
                return False
        return False

    def as_dict(self) -> Dict[str, Any]:
        return {
            'sensor': self.sensor,
            'threshold': self.threshold,
            'direction': self.direction,
            'weight': self.weight,
        }


# ================================================================
# КОНФИГ УРОВНЯ
# ================================================================

@dataclass
class LevelConfig:
    """Настройки одного уровня (FAST или SLOW)."""
    enabled: bool = True
    rules: List[Rule] = field(default_factory=list)
    min_score: int = 5

    # FAST-специфичные
    window_hours: int = 6
    baseline_hours: int = 24

    # SLOW-специфичные
    window_days: int = 10

    def __post_init__(self):
        if self.min_score < 1:
            raise ValueError(f"min_score={self.min_score} должен быть >= 1")

    def as_dict(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'min_score': self.min_score,
            'window_hours': self.window_hours,
            'baseline_hours': self.baseline_hours,
            'window_days': self.window_days,
            'rules': [r.as_dict() for r in self.rules],
        }


# ================================================================
# УРОВНИ СРОЧНОСТИ
# ================================================================

@dataclass
class UrgencyConfig:
    """Пороги для уровней срочности."""
    critical_score: int = 7
    high_score: int = 5
    medium_score: int = 3

    def __post_init__(self):
        if not (self.critical_score > self.high_score > self.medium_score):
            raise ValueError(
                "Пороги должны убывать: critical > high > medium. "
                f"Получено: critical={self.critical_score}, "
                f"high={self.high_score}, medium={self.medium_score}"
            )

    def classify(self, score: int) -> str:
        if score >= self.critical_score:
            return 'critical'
        if score >= self.high_score:
            return 'high'
        if score >= self.medium_score:
            return 'medium'
        return 'low'

    def as_dict(self) -> Dict[str, Any]:
        return {
            'critical_score': self.critical_score,
            'high_score': self.high_score,
            'medium_score': self.medium_score,
        }


# ================================================================
# ГЛАВНЫЙ КОНФИГ
# ================================================================

@dataclass
class PredictorConfig:
    """
    Полная конфигурация Predictor.

    Универсальный — правила задаются через YAML или программно.
    """
    # Метаданные
    name: str = "default"
    description: str = ""

    # Общие
    warmup_hours: int = 48
    points_per_hour: int = 3600

    # Уровни
    fast: LevelConfig = field(default_factory=lambda: LevelConfig(
        min_score=5,
        window_hours=6,
        baseline_hours=24,
    ))
    slow: LevelConfig = field(default_factory=lambda: LevelConfig(
        min_score=4,
        window_days=10,
    ))

    # Срочность
    urgency: UrgencyConfig = field(default_factory=UrgencyConfig)

    # Путь к конфигу (если загружен из файла)
    config_path: Optional[str] = None

    def __post_init__(self):
        if self.warmup_hours < 0:
            raise ValueError(f"warmup_hours={self.warmup_hours} должен быть >= 0")
        if self.points_per_hour <= 0:
            raise ValueError(f"points_per_hour={self.points_per_hour} должен быть > 0")

    # ============================================================
    # ВАЛИДАЦИЯ
    # ============================================================

    def validate_for_sensors(self, sensors: List[str]) -> List[str]:
        """Проверяет, что все датчики из правил есть в sensors."""
        warnings = []
        all_rules = self.fast.rules + self.slow.rules

        for rule in all_rules:
            matched = any(rule.matches_sensor(s) for s in sensors)
            if not matched:
                warnings.append(
                    f"Правило для '{rule.sensor}' не найдёт "
                    f"ни одного датчика. Доступные: {sensors[:5]}..."
                )

        return warnings

    # ============================================================
    # ЭКСПОРТ
    # ============================================================

    def as_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'warmup_hours': self.warmup_hours,
            'points_per_hour': self.points_per_hour,
            'fast': self.fast.as_dict(),
            'slow': self.slow.as_dict(),
            'urgency': self.urgency.as_dict(),
        }

    def to_yaml(self, path: str):
        """Сохранить в YAML."""
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump({'predictor': self.as_dict()}, f,
                      allow_unicode=True, sort_keys=False)
        print(f'💾 Конфиг сохранён: {path}')


# ================================================================
# ЗАГРУЗКА ИЗ YAML
# ================================================================

def _load_rule(data: Any) -> Rule:
    """Загружает одно правило."""
    if not isinstance(data, dict):
        raise ValueError(f"Правило должно быть словарём: {data}")

    if 'sensor' not in data or 'threshold' not in data:
        raise ValueError(f"Правило без sensor/threshold: {data}")

    return Rule(
        sensor=str(data['sensor']),
        threshold=float(data['threshold']),
        direction=data.get('direction', 'any'),
        weight=int(data.get('weight', 1)),
    )


def _load_level(data: Dict, level_type: str) -> LevelConfig:
    """Загружает один уровень (FAST / SLOW)."""
    if not isinstance(data, dict):
        data = {}

    rules = [_load_rule(r) for r in data.get('rules', [])]

    kwargs = {
        'enabled': data.get('enabled', True),
        'rules': rules,
        'min_score': int(data.get('min_score', 5)),
    }

    if level_type == 'fast':
        kwargs['window_hours'] = int(data.get('window_hours', 6))
        kwargs['baseline_hours'] = int(data.get('baseline_hours', 24))
    else:
        kwargs['window_days'] = int(data.get('window_days', 10))

    return LevelConfig(**kwargs)


def load_config_from_dict(data: Dict) -> PredictorConfig:
    """Загружает конфиг из словаря."""
    if not isinstance(data, dict):
        raise ValueError(
            f"Конфиг должен быть словарём: {type(data).__name__}"
        )

    # Поддерживаем {'predictor': {...}} или {...}
    pd = data.get('predictor', data)

    urgency_data = pd.get('urgency', {})

    return PredictorConfig(
        name=pd.get('name', 'default'),
        description=pd.get('description', ''),
        warmup_hours=int(pd.get('warmup_hours', 48)),
        points_per_hour=int(pd.get('points_per_hour', 3600)),
        fast=_load_level(pd.get('fast', {}), 'fast'),
        slow=_load_level(pd.get('slow', {}), 'slow'),
        urgency=UrgencyConfig(
            critical_score=int(urgency_data.get('critical_score', 7)),
            high_score=int(urgency_data.get('high_score', 5)),
            medium_score=int(urgency_data.get('medium_score', 3)),
        ),
    )


def load_predictor_config(path: str) -> PredictorConfig:
    """
    Загружает конфиг Predictor из YAML.

    Args:
        path: путь к YAML

    Returns:
        PredictorConfig
    """
    path_obj = Path(path)

    if not path_obj.exists():
        raise FileNotFoundError(f"Конфиг не найден: {path}")

    with open(path_obj, 'r', encoding='utf-8') as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Ошибка парсинга YAML {path}: {e}")

    if data is None:
        raise ValueError(f"Пустой YAML: {path}")

    config = load_config_from_dict(data)
    config.config_path = str(path_obj)

    return config


# ================================================================
# ШАБЛОН КОНФИГА
# ================================================================

CONFIG_TEMPLATE = """# Конфигурация Predictor
# ========================
# Заполните своими датчиками.

predictor:
  name: "My Installation"
  description: "Описание установки"
  
  warmup_hours: 48
  points_per_hour: 3600
  
  # FAST-уровень: острые аварии (1-6 часов)
  fast:
    enabled: true
    window_hours: 6
    baseline_hours: 24
    min_score: 5
    
    rules:
      # sensor    — имя датчика (точное или regex)
      # threshold — порог (0.05 = 5%)
      # direction — up | down | any
      # weight    — вес (1-10)
      
      - sensor: "sensor_name_1"
        threshold: 0.05
        direction: "up"
        weight: 3
      
      - sensor: "sensor_name_2"
        threshold: 0.05
        direction: "any"
        weight: 2
  
  # SLOW-уровень: медленная деградация (5-13 дней)
  slow:
    enabled: true
    window_days: 10
    min_score: 4
    
    rules:
      - sensor: "sensor_name_1"
        threshold: 0.15
        direction: "up"
        weight: 3
      
      - sensor: "sensor_name_2"
        threshold: 0.10
        direction: "up"
        weight: 2
  
  # Уровни срочности
  urgency:
    critical_score: 7
    high_score: 5
    medium_score: 3
"""


def create_config_template(output_path: str) -> str:
    """Создаёт шаблон конфига."""
    path_obj = Path(output_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(path_obj, 'w', encoding='utf-8') as f:
        f.write(CONFIG_TEMPLATE)

    print(f'📝 Шаблон конфига: {path_obj}')
    return str(path_obj)


# ================================================================
# PREDICTOR
# ================================================================

class AnomalyPredictor:
    """
    Двухуровневый Predictor аномалий.

    Использование:
        # 1. Из YAML
        predictor = AnomalyPredictor.from_config(
            'config.yaml', sensors=loader.sensors
        )

        # 2. Программно
        config = PredictorConfig(...)
        predictor = AnomalyPredictor(sensors=loader.sensors, config=config)

        # 3. Запуск
        result = predictor.predict(loader)
        result.print_alerts()
    """

    def __init__(self,
                 sensors: List[str],
                 config: Optional[PredictorConfig] = None):
        if not sensors:
            raise ValueError("sensors не может быть пустым")

        self.sensors = sensors
        self.n_sensors = len(sensors)
        self.config = config or PredictorConfig()

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
        """Считает score по правилам."""
        total_score = 0
        signals = []

        for rule in rules:
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
                    alerts.append(Alert(
                        t=i,
                        source=loader.source_at(i),
                        level='FAST',
                        score=score,
                        signals=signals,
                        urgency=cfg.urgency.classify(score),
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
                alerts.append(Alert(
                    t=mid,
                    source=b['source'],
                    level='SLOW',
                    score=score,
                    signals=signals,
                    urgency=cfg.urgency.classify(score),
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
