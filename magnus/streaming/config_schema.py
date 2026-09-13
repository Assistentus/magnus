# -*- coding: utf-8 -*-
"""
magnus/streaming/config_schema.py
====================================
УНИВЕРСАЛЬНАЯ схема конфига.

Поддерживает:
- sources, sensor_sets, events
- processor: alpha, n_sigma, min_count, degree, path_length,
             window_size, overlap
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml


# ================================================================
# СХЕМА
# ================================================================

@dataclass
class ProcessorConfig:
    """
    Параметры процессора.
    """
    alpha: float = 0.05
    n_sigma: float = 1.5
    min_count: int = 2
    degree: int = 3
    path_length: int = 0        # 0 = auto = degree + 1
    window_size: int = 0        # 0 = без reset
    overlap: int = 0            # нахлёст между окнами

    def __post_init__(self):
        if not (0.0 < self.alpha <= 1.0):
            raise ValueError(f"alpha={self.alpha} должен быть в (0, 1]")
        if self.n_sigma <= 0:
            raise ValueError(f"n_sigma={self.n_sigma} должен быть > 0")
        if self.min_count < 1:
            raise ValueError(f"min_count={self.min_count} должен быть >= 1")
        if self.degree < 1:
            raise ValueError(f"degree={self.degree} должен быть >= 1")

        if self.path_length == 0:
            self.path_length = self.degree + 1
        if self.path_length < self.degree + 1:
            self.path_length = self.degree + 1

        if self.window_size < 0:
            raise ValueError(f"window_size={self.window_size} должен быть >= 0")
        if self.window_size == 1:
            raise ValueError("window_size=1 бессмысленен")

        if self.overlap < 0:
            raise ValueError(f"overlap={self.overlap} должен быть >= 0")

        if self.window_size > 0 and self.overlap >= self.window_size:
            raise ValueError(
                f"overlap ({self.overlap}) должен быть < "
                f"window_size ({self.window_size})"
            )

    def effective_path_length(self) -> int:
        return max(self.path_length, self.degree + 1)

    @property
    def has_windows(self) -> bool:
        return self.window_size > 0

    @property
    def has_overlap(self) -> bool:
        return self.overlap > 0 and self.window_size > 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            'alpha': self.alpha,
            'n_sigma': self.n_sigma,
            'min_count': self.min_count,
            'degree': self.degree,
            'path_length': self.path_length,
            'window_size': self.window_size,
            'overlap': self.overlap,
        }


@dataclass
class SensorSet:
    name: str
    columns: List[str]
    description: str = ""

    def __post_init__(self):
        if not self.columns:
            raise ValueError(f"Набор '{self.name}' не содержит колонок")
        seen = set()
        for c in self.columns:
            if not isinstance(c, str) or not c.strip():
                raise ValueError(f"Недопустимое имя колонки в '{self.name}': {c!r}")
            if c in seen:
                raise ValueError(f"Дубликат колонки в '{self.name}': {c!r}")
            seen.add(c)

    def __len__(self) -> int:
        return len(self.columns)


@dataclass
class SourceConfig:
    path: str
    pattern: str = "*.csv"
    format: str = "auto"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.path:
            raise ValueError("SourceConfig.path не может быть пустым")
        allowed = ['auto', 'csv', 'tsv', 'parquet', 'excel']
        if self.format not in allowed:
            raise ValueError(
                f"Формат '{self.format}' не поддерживается. Допустимые: {allowed}"
            )


@dataclass
class MagnusConfig:
    name: str
    sources: List[SourceConfig]
    sensor_sets: Dict[str, SensorSet]
    processor: ProcessorConfig = field(default_factory=ProcessorConfig)
    events: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    config_path: Optional[str] = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("MagnusConfig.name не может быть пустым")
        if not self.sensor_sets:
            raise ValueError("MagnusConfig должен содержать хотя бы один sensor_set")

    def get_sensor_set(self, name: str) -> SensorSet:
        if name not in self.sensor_sets:
            raise ValueError(
                f"Набор '{name}' не найден. "
                f"Доступные: {list(self.sensor_sets.keys())}"
            )
        return self.sensor_sets[name]

    def get_event(self, key: str) -> str:
        return self.events.get(str(key), '')

    def list_sensor_sets(self) -> List[str]:
        return list(self.sensor_sets.keys())

    def list_sources(self) -> List[str]:
        return [s.path for s in self.sources]

    def info(self) -> str:
        lines = [
            f"{'='*60}",
            f"Конфиг: {self.name}",
            f"{'='*60}",
        ]
        if self.metadata.get('description'):
            lines.append(f"Описание: {self.metadata['description']}")
        if self.config_path:
            lines.append(f"Путь: {self.config_path}")

        lines.append(f"\nИсточников: {len(self.sources)}")
        for i, src in enumerate(self.sources):
            lines.append(f"  [{i}] {src.path}")
            lines.append(f"      pattern: {src.pattern}, format: {src.format}")

        lines.append(f"\nНаборы датчиков: {len(self.sensor_sets)}")
        for name, ss in self.sensor_sets.items():
            desc = f" — {ss.description}" if ss.description else ""
            lines.append(f"  {name:<15} ({len(ss.columns)} датчиков){desc}")

        if self.events:
            lines.append(f"\nСобытий: {len(self.events)}")
            for key, val in list(self.events.items())[:5]:
                lines.append(f"  {key}: {val}")
            if len(self.events) > 5:
                lines.append(f"  ... и ещё {len(self.events) - 5}")

        lines.append(f"\nПроцессор:")
        p = self.processor
        lines.append(f"  alpha:       {p.alpha}")
        lines.append(f"  n_sigma:     {p.n_sigma}")
        lines.append(f"  min_count:   {p.min_count}")
        lines.append(f"  degree:      {p.degree}")
        lines.append(f"  path_length: {p.effective_path_length()}")
        window_str = (
            f"{p.window_size} (оконный режим)"
            if p.has_windows else "0 (накопительный)"
        )
        lines.append(f"  window_size: {window_str}")
        if p.has_overlap:
            lines.append(f"  overlap:     {p.overlap} "
                         f"({100*p.overlap//p.window_size}%)")

        return "\n".join(lines)

    def as_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'sources': [
                {
                    'path': s.path,
                    'pattern': s.pattern,
                    'format': s.format,
                    'metadata': s.metadata,
                }
                for s in self.sources
            ],
            'sensor_sets': {
                name: {
                    'columns': ss.columns,
                    'description': ss.description,
                }
                for name, ss in self.sensor_sets.items()
            },
            'processor': self.processor.as_dict(),
            'events': self.events,
            'metadata': self.metadata,
        }


# ================================================================
# ЗАГРУЗКА
# ================================================================

def load_config_from_dict(data: Dict) -> MagnusConfig:
    if not isinstance(data, dict):
        raise ValueError(
            f"Конфиг должен быть словарём, получено: {type(data).__name__}"
        )

    name = data.get('name', 'unnamed')

    sources_data = data.get('sources', [])
    sources: List[SourceConfig] = []

    if isinstance(sources_data, str):
        sources = [SourceConfig(path=sources_data)]
    elif isinstance(sources_data, list):
        for s in sources_data:
            if isinstance(s, str):
                sources.append(SourceConfig(path=s))
            elif isinstance(s, dict):
                sources.append(SourceConfig(
                    path=s['path'],
                    pattern=s.get('pattern', '*.csv'),
                    format=s.get('format', 'auto'),
                    metadata=s.get('metadata', {}),
                ))
            else:
                raise ValueError(f"Некорректный источник: {s!r}")
    elif sources_data:
        raise ValueError(
            f"sources должен быть строкой или списком, "
            f"получено: {type(sources_data).__name__}"
        )

    sensor_sets: Dict[str, SensorSet] = {}
    for ss_name, ss_data in data.get('sensor_sets', {}).items():
        if isinstance(ss_data, list):
            sensor_sets[ss_name] = SensorSet(name=ss_name, columns=ss_data)
        elif isinstance(ss_data, dict):
            sensor_sets[ss_name] = SensorSet(
                name=ss_name,
                columns=ss_data.get('columns', []),
                description=ss_data.get('description', ''),
            )
        else:
            raise ValueError(f"Некорректный sensor_set '{ss_name}': {ss_data!r}")

    if not sensor_sets:
        raise ValueError("Конфиг должен содержать хотя бы один sensor_set")

    proc_data = data.get('processor', {})
    processor = ProcessorConfig(
        alpha=proc_data.get('alpha', 0.05),
        n_sigma=proc_data.get('n_sigma', 1.5),
        min_count=proc_data.get('min_count', 2),
        degree=proc_data.get('degree', 3),
        path_length=proc_data.get('path_length', 0),
        window_size=proc_data.get('window_size', 0),
        overlap=proc_data.get('overlap', 0),
    )

    events_raw = data.get('events', {})
    events = {str(k): str(v) for k, v in events_raw.items()}
    metadata = data.get('metadata', {})

    return MagnusConfig(
        name=name,
        sources=sources,
        sensor_sets=sensor_sets,
        processor=processor,
        events=events,
        metadata=metadata,
    )


def load_config(path: str) -> MagnusConfig:
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Конфиг не найден: {path}")
    if not path_obj.is_file():
        raise ValueError(f"Путь не является файлом: {path}")

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

CONFIG_TEMPLATE = """# Конфигурация Magnus
# =====================

name: "My Installation"
description: "Описание установки"

sources:
  - path: "/path/to/data"
    pattern: "*.csv"
    format: "auto"

sensor_sets:
  default:
    columns:
      - "sensor1"
      - "sensor2"
      - "sensor3"

events:
  "2026-01-01": "Плановое ТО"

# Параметры процессора
processor:
  alpha: 0.05           # EMA коэффициент (0 < alpha <= 1)
  n_sigma: 1.5          # порог квантования в сигмах
  min_count: 2          # минимум повторов для отношения
  degree: 2             # степень Magnus (1..N)
  path_length: 0        # 0 = auto = degree + 1
  window_size: 0        # 0 = накопительный режим
                        # > 0 = оконный режим: rank_tracker и state_graph
                        #   сбрасываются каждые window_size точек.
  overlap: 0            # 0 = окна не пересекаются
                        # > 0 = нахлёст (должен быть < window_size).
                        #   Сохраняет контекст на границах окон.
                        #   Рекомендуется 10-20% от window_size.
"""


def create_config_template(output_path: str) -> str:
    path_obj = Path(output_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    with open(path_obj, 'w', encoding='utf-8') as f:
        f.write(CONFIG_TEMPLATE)
    return str(path_obj)


# ================================================================
# ВАЛИДАЦИЯ
# ================================================================

def validate_config(config: MagnusConfig) -> List[str]:
    warnings = []

    for i, src in enumerate(config.sources):
        path = Path(src.path)
        if not path.exists():
            warnings.append(f"⚠️ Источник [{i}] не существует: {src.path}")

    p = config.processor
    if p.path_length < p.degree + 1 and p.path_length != 0:
        warnings.append(
            f"⚠️ path_length ({p.path_length}) < degree + 1 "
            f"({p.degree + 1}). Будет использовано path_length = {p.degree + 1}"
        )

    if p.has_windows and p.window_size < 1000:
        warnings.append(
            f"⚠️ window_size={p.window_size} — малое окно. "
            f"Рекомендуется >= 10000."
        )

    if p.has_overlap:
        pct = 100 * p.overlap / p.window_size
        if pct > 50:
            warnings.append(
                f"⚠️ overlap={p.overlap} ({pct:.0f}%) — большой нахлёст. "
                f"Рекомендуется 10-20%."
            )

    for name, ss in config.sensor_sets.items():
        if len(ss.columns) < 2:
            warnings.append(
                f"⚠️ Набор '{name}' содержит только {len(ss.columns)} датчик. "
                f"Для работы нужно минимум 2."
            )

    return warnings