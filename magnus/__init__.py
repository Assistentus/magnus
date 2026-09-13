# -*- coding: utf-8 -*-
"""
magnus: Вычислительная гомологическая алгебра.

Базовые компоненты:
    MagnusAlgebra    — алгебра Магнуса
    FRCodeRegistry   — реестр fr-кодов
    HomologySolver   — решатель гомологий
    TextPresentation — построение копредставлений из текста

Streaming-ядро:
    StreamingMagnus    — низкоуровневый процессор (Rust)
    StreamingPipeline  — универсальный pipeline
    UniversalRunner    — runner по YAML-конфигу
    AutoDetectLoader   — загрузчик с автоопределением формата
    FileSource         — источник данных из файлов
    StreamSource       — базовый класс источника
    load_config        — загрузка YAML-конфига
    create_config_template — создать шаблон конфига
"""

# ================================================================
# БАЗОВЫЕ КОМПОНЕНТЫ
# ================================================================

from .presentation import TextPresentation
from .magnus import MagnusAlgebra
from .codes import FRCodeRegistry
from .solver import HomologySolver


# ================================================================
# STREAMING-ЯДРО
# ================================================================

from .streaming import (
    # Rust
    StreamingMagnus,
    
    # Ядро
    StreamingPipeline,
    UniversalRunner,
    
    # Конфиг
    load_config,
    create_config_template,
    
    # Загрузчики
    AutoDetectLoader,
    
    # Источники
    FileSource,
    StreamSource,
)


# ================================================================
# ВЕРСИЯ И ЭКСПОРТ
# ================================================================

__version__ = "0.3.0"

__all__ = [
    # Базовые
    "TextPresentation",
    "MagnusAlgebra",
    "FRCodeRegistry",
    "HomologySolver",
    
    # Streaming
    "StreamingMagnus",
    "StreamingPipeline",
    "UniversalRunner",
    "load_config",
    "create_config_template",
    "AutoDetectLoader",
    "FileSource",
    "StreamSource",
]
