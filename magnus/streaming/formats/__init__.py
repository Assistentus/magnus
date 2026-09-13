# -*- coding: utf-8 -*-
"""
magnus/streaming/formats
=========================
Загрузчики данных для разных форматов.
"""

from .base import BaseLoader
from .auto_detect import (
    AutoDetectLoader,
    detect_encoding,
    detect_delimiter,
    detect_decimal,
    detect_line_ending,
)
from .npy_concatenated import NPYConcatenatedLoader

__all__ = [
    'BaseLoader',
    'AutoDetectLoader',
    'NPYConcatenatedLoader',
    'detect_encoding',
    'detect_delimiter',
    'detect_decimal',
    'detect_line_ending',
]
