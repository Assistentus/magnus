# -*- coding: utf-8 -*-
"""
magnus/streaming/sources
=========================
Источники потоковых данных.

Каждый источник реализует интерфейс StreamSource.
"""

from .base import StreamSource
from .file_source import FileSource

# Опциональные (требуют зависимостей)
try:
    from .opcua_source import OPCUASource
except ImportError:
    OPCUASource = None

try:
    from .modbus_source import ModbusSource
except ImportError:
    ModbusSource = None

try:
    from .mqtt_source import MQTTSource
except ImportError:
    MQTTSource = None


__all__ = [
    'StreamSource',
    'FileSource',
    'OPCUASource',
    'ModbusSource',
    'MQTTSource',
]