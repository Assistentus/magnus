# -*- coding: utf-8 -*-
"""
magnus.streaming
=================
УНИВЕРСАЛЬНАЯ потоковая обработка данных + предсказание аномалий.

Не знает про конкретные установки (турбины, двигатели, реакторы).

Основные компоненты:
    StreamingMagnus       — низкоуровневый Rust-процессор
    StreamingPipeline     — высокоуровневый pipeline
    AnomalyPredictor      — предсказание аномалий (FAST + SLOW)
    generate_full_report  — автоматический отчёт с графиками

Пример использования:

    from magnus.streaming import (
        NPYConcatenatedLoader,
        AnomalyPredictor,
        generate_full_report,
    )

    # 1. Загрузка данных
    loader = NPYConcatenatedLoader(data_dir='data/my_installation')

    # 2. Predictor из YAML-конфига
    predictor = AnomalyPredictor.from_config(
        config_path='examples/my_config.yaml',
        sensors=loader.sensors,
    )

    # 3. Запуск и отчёт
    result = predictor.predict(loader)
    result.print_alerts()

    generate_full_report(
        predictor_result=result,
        loader=loader,
        output_dir='output/',
    )
"""

# ================================================================
# НИЗКОУРОВНЕВЫЙ RUST-КЛАСС
# ================================================================

try:
    from fr_rank_rs import StreamingMagnus
    RUST_AVAILABLE = True
except ImportError:
    StreamingMagnus = None
    RUST_AVAILABLE = False


# ================================================================
# ЯДРО PIPELINE
# ================================================================

from .pipeline import (
    StreamingPipeline,
    DayResult,
    ProcessingResult,
    WindowFingerprint,
)


# ================================================================
# СХЕМА КОНФИГА ПАЙПЛАЙНА
# ================================================================

from .config_schema import (
    MagnusConfig,
    ProcessorConfig,
    SensorSet,
    SourceConfig,
    load_config,
    load_config_from_dict,
    create_config_template,
    validate_config,
)


# ================================================================
# RUNNER
# ================================================================

from .runner import UniversalRunner, create_loader


# ================================================================
# ЗАГРУЗЧИКИ (formats)
# ================================================================

from .formats import (
    BaseLoader,
    AutoDetectLoader,
    NPYConcatenatedLoader,
    detect_encoding,
    detect_delimiter,
    detect_decimal,
    detect_line_ending,
)


# ================================================================
# ИСТОЧНИКИ (sources)
# ================================================================

from .sources import (
    StreamSource,
    FileSource,
    OPCUASource,
    ModbusSource,
    MQTTSource,
)


# ================================================================
# PREDICTOR (предсказание аномалий)
# ================================================================

from .predictor import (
    AnomalyPredictor,
    PredictionResult,
    Alert,
)
from .predictor_config import (
    PredictorConfig,
    Rule,
    LevelConfig,
    UrgencyConfig,
    load_predictor_config,
    create_config_template as create_predictor_config_template,
)


# ================================================================
# VISUALIZER (визуализация)
# ================================================================

from .visualizer import (
    generate_full_report,
    plot_alerts_timeline,
    plot_alerts_by_source,
    plot_sensors_degradation,
    plot_sensor_around_event,
)


# ================================================================
# ЭКСПОРТ
# ================================================================

__all__ = [
    # === Rust ===
    'StreamingMagnus',
    'RUST_AVAILABLE',

    # === Ядро pipeline ===
    'StreamingPipeline',
    'DayResult',
    'ProcessingResult',
    'WindowFingerprint',

    # === Схема конфига pipeline ===
    'MagnusConfig',
    'ProcessorConfig',
    'SensorSet',
    'SourceConfig',
    'load_config',
    'load_config_from_dict',
    'create_config_template',
    'validate_config',

    # === Runner ===
    'UniversalRunner',
    'create_loader',

    # === Загрузчики ===
    'BaseLoader',
    'AutoDetectLoader',
    'NPYConcatenatedLoader',
    'detect_encoding',
    'detect_delimiter',
    'detect_decimal',
    'detect_line_ending',

    # === Источники ===
    'StreamSource',
    'FileSource',
    'OPCUASource',
    'ModbusSource',
    'MQTTSource',

    # === Predictor ===
    'AnomalyPredictor',
    'PredictionResult',
    'Alert',
    'PredictorConfig',
    'Rule',
    'LevelConfig',
    'UrgencyConfig',
    'load_predictor_config',
    'create_predictor_config_template',

    # === Visualizer ===
    'generate_full_report',
    'plot_alerts_timeline',
    'plot_alerts_by_source',
    'plot_sensors_degradation',
    'plot_sensor_around_event',
]
