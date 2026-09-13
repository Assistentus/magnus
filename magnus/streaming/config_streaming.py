# -*- coding: utf-8 -*-
"""
magnus/streaming/predictor_config.py
======================================
Схема и загрузка конфига Predictor из YAML.

Универсальная схема — не знает про конкретные установки.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
import re
import yaml


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
        # Валидация
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
        # Точное совпадение
        if self.sensor == sensor_name:
            return True
        # Regex (если в паттерне есть спецсимволы)
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
# КОНФИГ УРОВНЯ (FAST / SLOW)
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
        if self.window_hours <= 0:
            raise ValueError(f"window_hours={self.window_hours} должен быть > 0")
        if self.baseline_hours <= 0:
            raise ValueError(f"baseline_hours={self.baseline_hours} должен быть > 0")
        if self.window_days <= 0:
            raise ValueError(f"window_days={self.window_days} должен быть > 0")
    
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
        """Определяет уровень срочности по score."""
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
    
    Загружается из YAML или создаётся программно.
    """
    # Общие
    warmup_hours: int = 48
    points_per_hour: int = 3600
    
    # Уровни
    fast: LevelConfig = field(default_factory=LevelConfig)
    slow: LevelConfig = field(default_factory=LevelConfig)
    
    # Срочность
    urgency: UrgencyConfig = field(default_factory=UrgencyConfig)
    
    # Метаданные
    name: str = "default"
    description: str = ""
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
        """
        Проверяет, что все датчики из правил есть в sensors.
        
        Returns:
            Список предупреждений (пустой если всё OK).
        """
        warnings = []
        all_rules = (
            self.fast.rules + self.slow.rules
        )
        
        for rule in all_rules:
            matched = any(rule.matches_sensor(s) for s in sensors)
            if not matched:
                warnings.append(
                    f"Правило для '{rule.sensor}' не найдёт "
                    f"ни одного датчика. Доступные: {sensors[:5]}..."
                )
        
        return warnings
    
    def get_active_rules_for_sensor(self, sensor: str) -> List[Rule]:
        """Все правила, применимые к датчику."""
        return [
            r for r in (self.fast.rules + self.slow.rules)
            if r.matches_sensor(sensor)
        ]
    
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
            yaml.dump(self.as_dict(), f, allow_unicode=True, sort_keys=False)
        print(f'💾 Конфиг сохранён: {path}')


# ================================================================
# ЗАГРУЗКА ИЗ СЛОВАРЯ
# ================================================================

def _load_rule(data: Dict) -> Rule:
    """Загружает одно правило из словаря."""
    if not isinstance(data, dict):
        raise ValueError(f"Правило должно быть словарём, получено: {type(data).__name__}")
    
    if 'sensor' not in data:
        raise ValueError(f"У правила нет 'sensor': {data}")
    if 'threshold' not in data:
        raise ValueError(f"У правила нет 'threshold': {data}")
    
    return Rule(
        sensor=data['sensor'],
        threshold=float(data['threshold']),
        direction=data.get('direction', 'any'),
        weight=int(data.get('weight', 1)),
    )


def _load_level(data: Dict, level_type: str) -> LevelConfig:
    """Загружает настройки одного уровня (FAST / SLOW)."""
    if not isinstance(data, dict):
        data = {}
    
    rules_data = data.get('rules', [])
    rules = [_load_rule(r) for r in rules_data]
    
    kwargs = {
        'enabled': data.get('enabled', True),
        'rules': rules,
        'min_score': int(data.get('min_score', 5)),
    }
    
    if level_type == 'fast':
        kwargs['window_hours'] = int(data.get('window_hours', 6))
        kwargs['baseline_hours'] = int(data.get('baseline_hours', 24))
    elif level_type == 'slow':
        kwargs['window_days'] = int(data.get('window_days', 10))
    
    return LevelConfig(**kwargs)


def load_config_from_dict(data: Dict) -> PredictorConfig:
    """
    Загружает конфиг из словаря.
    
    Args:
        data: словарь с ключом 'predictor' (или без него)
    
    Returns:
        PredictorConfig
    """
    if not isinstance(data, dict):
        raise ValueError(
            f"Конфиг должен быть словарём, получено: {type(data).__name__}"
        )
    
    # Поддерживаем как {'predictor': {...}}, так и {...}
    predictor_data = data.get('predictor', data)
    
    # Уровни
    fast_data = predictor_data.get('fast', {})
    slow_data = predictor_data.get('slow', {})
    
    fast = _load_level(fast_data, 'fast')
    slow = _load_level(slow_data, 'slow')
    
    # Срочность
    urgency_data = predictor_data.get('urgency', {})
    urgency = UrgencyConfig(
        critical_score=int(urgency_data.get('critical_score', 7)),
        high_score=int(urgency_data.get('high_score', 5)),
        medium_score=int(urgency_data.get('medium_score', 3)),
    )
    
    # Общие
    return PredictorConfig(
        name=predictor_data.get('name', 'default'),
        description=predictor_data.get('description', ''),
        warmup_hours=int(predictor_data.get('warmup_hours', 48)),
        points_per_hour=int(predictor_data.get('points_per_hour', 3600)),
        fast=fast,
        slow=slow,
        urgency=urgency,
    )


# ================================================================
# ЗАГРУЗКА ИЗ YAML
# ================================================================

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
# ШАБЛОН
# ================================================================

CONFIG_TEMPLATE = """# Конфигурация Predictor
# ========================
# Универсальная схема — заполните своими датчиками.

predictor:
  name: "My Installation"
  description: "Описание установки"
  
  # Общие настройки
  warmup_hours: 48          # Игнорировать первые N часов работы
  points_per_hour: 3600     # Частота сигнала (1 Гц = 3600 точек/час)
  
  # FAST-уровень: острые аварии (1-6 часов)
  fast:
    enabled: true
    window_hours: 6         # Окно текущего состояния
    baseline_hours: 24      # Окно базовой линии
    min_score: 5            # Минимум для алерта
    
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
        direction: "up"
        weight: 2
      
      - sensor: "sensor_name_3"
        threshold: 0.03
        direction: "any"
        weight: 1
  
  # SLOW-уровень: медленная деградация (5-13 дней)
  slow:
    enabled: true
    window_days: 10         # Окно сравнения
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
      
      - sensor: "sensor_name_3"
        threshold: 0.05
        direction: "down"
        weight: 2
  
  # Уровни срочности (по score)
  urgency:
    critical_score: 7       # score >= 7 → critical
    high_score: 5           # score >= 5 → high
    medium_score: 3         # score >= 3 → medium
"""


def create_config_template(output_path: str) -> str:
    """Создаёт шаблон конфига."""
    path_obj = Path(output_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path_obj, 'w', encoding='utf-8') as f:
        f.write(CONFIG_TEMPLATE)
    
    print(f'📝 Шаблон конфига: {path_obj}')
    return str(path_obj)
