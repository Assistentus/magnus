# -*- coding: utf-8 -*-
"""
magnus.streaming
=================
УНИВЕРСАЛЬНОЕ ядро потоковой обработки.

НЕ знает про конкретные системы.

Пример:
    from magnus.streaming import (
        StreamingPipeline, AutoDetectLoader, NPYConcatenatedLoader,
        AnomalyPredictor, generate_full_report,
    )

    # 1. Основная обработка
    loader = NPYConcatenatedLoader(data_dir='data/kadvi_007_npy')
    pipeline = StreamingPipeline(
        sensors=loader.sensors,
        loader=loader,
        degree=2,
    )
    result = pipeline.process_concatenated_npy(loader)

    # 2. Предсказание аномалий
    predictor = AnomalyPredictor(sensors=loader.sensors)
    predictions = predictor.predict(loader)
    predictions.print_alerts()

    # 3. Отчёт с визуализациями
    generate_full_report(predictions, loader, 'magnus_output/kadvi_007')
"""

# Rust-класс
try:
    from fr_rank_rs import StreamingMagnus
    RUST_AVAILABLE = True
except ImportError:
    StreamingMagnus = None
    RUST_AVAILABLE = False


# ================================================================
# ЯДРО
# ================================================================

from .pipeline import (
    StreamingPipeline,
    DayResult,
    ProcessingResult,
    WindowFingerprint,
)


# ================================================================
# СХЕМА КОНФИГА
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
    PredictorConfig,
    PredictionResult,
    Alert,
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
    # Rust
    'StreamingMagnus',
    'RUST_AVAILABLE',

    # Ядро
    'StreamingPipeline',
    'DayResult',
    'ProcessingResult',
    'WindowFingerprint',

    # Схема
    'MagnusConfig',
    'ProcessorConfig',
    'SensorSet',
    'SourceConfig',
    'load_config',
    'load_config_from_dict',
    'create_config_template',
    'validate_config',

    # Runner
    'UniversalRunner',
    'create_loader',

    # Загрузчики
    'BaseLoader',
    'AutoDetectLoader',
    'NPYConcatenatedLoader',
    'detect_encoding',
    'detect_delimiter',
    'detect_decimal',
    'detect_line_ending',

    # Источники
    'StreamSource',
    'FileSource',
    'OPCUASource',
    'ModbusSource',
    'MQTTSource',

    # Predictor
    'AnomalyPredictor',
    'PredictorConfig',
    'PredictionResult',
    'Alert',

    # Visualizer
    'generate_full_report',
    'plot_alerts_timeline',
    'plot_alerts_by_source',
    'plot_sensors_degradation',
    'plot_sensor_around_event',
]