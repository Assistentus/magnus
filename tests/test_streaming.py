# tests/test_streaming.py
# ===================================================================
# Тесты потокового процессора.
# ===================================================================

import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from magnus.streaming import StreamingMagnus


def test_create():
    proc = StreamingMagnus(n_sensors=3)
    assert proc.n_sensors == 3
    assert proc.rank == 0
    assert proc.n_states == 0


def test_single_point():
    proc = StreamingMagnus(n_sensors=3)
    result = proc.process(np.array([1.0, 2.0, 3.0]))
    assert result['n_states'] >= 1


def test_monotonic_rank():
    """Ранг не должен убывать."""
    proc = StreamingMagnus(n_sensors=2, min_count=2)
    ranks = []

    for i in range(1000):
        x = np.array([np.sin(i * 0.1), np.cos(i * 0.1)])
        result = proc.process(x)
        ranks.append(result['rank'])

    # Ранг монотонно не убывает
    for i in range(1, len(ranks)):
        assert ranks[i] >= ranks[i - 1], f"Ранг убыл на шаге {i}"


def test_rank_grows_on_patterns():
    """На повторяющихся паттернах ранг должен расти."""
    proc = StreamingMagnus(n_sensors=2, min_count=2)

    # 100 раз повторяем паттерн из 2 состояний
    pattern = [
        np.array([1.0, 1.0]),
        np.array([-1.0, -1.0]),
    ]

    for i in range(100):
        proc.process(pattern[i % 2])

    assert proc.rank > 0, "Ранг не вырос на повторах"
    assert proc.n_states >= 2


def test_batch():
    proc = StreamingMagnus(n_sensors=3)
    data = np.random.randn(1000, 3)
    n = proc.process_batch(data)
    assert n == 1000
    assert proc.n_states > 0


def test_reset():
    proc = StreamingMagnus(n_sensors=3)

    for i in range(100):
        proc.process(np.random.randn(3))

    rank_before = proc.rank
    assert rank_before > 0

    proc.reset()

    assert proc.rank == 0
    assert proc.n_states == 0
    assert proc.n_transitions == 0


def test_adaptive_quantization():
    """Адаптивное квантование: одинаковые данные → одно состояние."""
    proc = StreamingMagnus(n_sensors=2, alpha=0.1, n_sigma=3.0)

    # Одинаковые точки
    for _ in range(100):
        proc.process(np.array([1.0, 1.0]))

    # Должно быть одно состояние (все точки одинаковы)
    assert proc.n_states == 1


def test_detects_change():
    """При изменении сигнала появляются новые состояния."""
    proc = StreamingMagnus(n_sensors=1, alpha=0.1, n_sigma=1.0)

    # Стабильный сигнал
    for _ in range(100):
        proc.process(np.array([1.0]))

    states_before = proc.n_states

    # Резкое изменение
    for _ in range(100):
        proc.process(np.array([100.0]))

    states_after = proc.n_states

    assert states_after > states_before, \
        "Не обнаружено изменение сигнала"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])