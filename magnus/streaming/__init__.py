# -*- coding: utf-8 -*-
"""
magnus.streaming
=================
Потоковая обработка данных через StreamingMagnus + StreamingPipeline.

Экспортирует:
- StreamingMagnus — низкоуровневый Rust-класс (прямая обёртка)
- StreamingPipeline — высокоуровневый pipeline (готовые сценарии)
"""

# ================================================================
# Низкоуровневый Rust-класс
# ================================================================

try:
    from fr_rank_rs import StreamingMagnus
    RUST_AVAILABLE = True
except ImportError:
    StreamingMagnus = None
    RUST_AVAILABLE = False


# ================================================================
# Высокоуровневый pipeline
# ================================================================

from .streaming_pipeline import (
    StreamingPipeline,
    DayResult,
    ProcessingResult,
)


__all__ = [
    'StreamingMagnus',
    'StreamingPipeline',
    'DayResult',
    'ProcessingResult',
    'RUST_AVAILABLE',
]
