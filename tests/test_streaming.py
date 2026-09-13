# tests/test_streaming.py
# ===================================================================
# Тесты потокового процессора.
# ===================================================================

import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from fr_rank_rs import StreamingMagnus
except ImportError:
    StreamingMagnus = None
    pytestmark = pytest.mark.skip(reason="fr_rank_rs not built")


@pytest.mark.skipif(StreamingMagnus is None, reason="fr_rank_rs not built")
class TestStreamingMagnus:
    """Тесты для StreamingMagnus (актуальный API)."""

    def test_create(self):
        proc = StreamingMagnus(n_sensors=3)
        assert proc.n_sensors == 3
        assert proc.get_rank() == 0
        assert proc.get_n_states() == 0

    def test_create_with_params(self):
        proc = StreamingMagnus(
            n_sensors=12,
            alpha=0.05,
            n_sigma=1.5,
            min_count=2,
            degree=2,
            path_length=3,
        )
        assert proc.n_sensors == 12
        assert proc.get_degree() == 2
        assert proc.get_path_length() == 3

    def test_single_point(self):
        proc = StreamingMagnus(n_sensors=3)
        result = proc.process(np.array([1.0, 2.0, 3.0]))
        assert result['n_states'] >= 1
        assert result['t'] == 1

    def test_monotonic_rank(self):
        """Ранг не должен убывать."""
        proc = StreamingMagnus(n_sensors=2, min_count=2)
        ranks = []

        for i in range(1000):
            x = np.array([np.sin(i * 0.1), np.cos(i * 0.1)])
            result = proc.process(x)
            ranks.append(result['rank'])

        for i in range(1, len(ranks)):
            assert ranks[i] >= ranks[i - 1], f"Ранг убыл на шаге {i}"

    def test_rank_grows_on_patterns(self):
        """На повторяющихся паттернах ранг должен расти."""
        proc = StreamingMagnus(n_sensors=2, min_count=2)

        pattern = [
            np.array([1.0, 1.0]),
            np.array([-1.0, -1.0]),
        ]

        for i in range(100):
            proc.process(pattern[i % 2])

        assert proc.get_rank() > 0, "Ранг не вырос на повторах"
        assert proc.get_n_states() >= 2

    def test_batch_fast(self):
        """Batch через process_batch_fast (плоский массив)."""
        proc = StreamingMagnus(n_sensors=3)
        n_points = 1000
        data = np.random.randn(n_points * 3).astype(np.float64)
        proc.process_batch_fast(data, n_points)
        assert proc.get_t() == n_points
        assert proc.get_n_states() > 0

    def test_batch(self):
        """Batch через process_batch."""
        proc = StreamingMagnus(n_sensors=3)
        n_points = 1000
        data = np.random.randn(n_points * 3).astype(np.float64)
        n = proc.process_batch(data, n_points)
        assert n == n_points
        assert proc.get_n_states() > 0

    def test_reset(self):
        proc = StreamingMagnus(n_sensors=3)

        for i in range(100):
            proc.process(np.random.randn(3))

        assert proc.get_rank() > 0

        proc.reset()

        assert proc.get_rank() == 0
        assert proc.get_n_states() == 0
        assert proc.get_n_transitions() == 0
        assert proc.get_t() == 0

    def test_adaptive_quantization(self):
        """Одинаковые данные → одно состояние."""
        proc = StreamingMagnus(n_sensors=2, alpha=0.1, n_sigma=3.0)

        for _ in range(100):
            proc.process(np.array([1.0, 1.0]))

        assert proc.get_n_states() == 1

    def test_detects_change(self):
        """При изменении сигнала появляются новые состояния."""
        proc = StreamingMagnus(n_sensors=1, alpha=0.1, n_sigma=1.0)

        for _ in range(100):
            proc.process(np.array([1.0]))

        states_before = proc.get_n_states()

        for _ in range(100):
            proc.process(np.array([100.0]))

        states_after = proc.get_n_states()

        assert states_after > states_before, \
            "Не обнаружено изменение сигнала"

    def test_window_mode(self):
        """Оконный режим: окна закрываются."""
        proc = StreamingMagnus(
            n_sensors=2,
            window_size=100,
            overlap=10,
            degree=2,
            path_length=3,
        )

        for i in range(500):
            x = np.array([np.sin(i * 0.1), np.cos(i * 0.1)])
            proc.process(x)

        assert proc.get_n_windows_closed() >= 4
        fps = proc.get_window_fingerprints()
        assert len(fps) >= 4

    def test_flush(self):
        """Принудительное закрытие хвостового окна."""
        proc = StreamingMagnus(
            n_sensors=2,
            window_size=100,
            degree=2,
            path_length=3,
        )

        for i in range(50):
            x = np.array([np.sin(i * 0.1), np.cos(i * 0.1)])
            proc.process(x)

        assert proc.get_n_windows_closed() == 0

        flushed = proc.flush()
        assert flushed is True
        assert proc.get_n_windows_closed() == 1

    def test_fast_layer_disabled(self):
        """FAST по умолчанию выключен."""
        proc = StreamingMagnus(n_sensors=2, degree=2)
        assert proc.get_fast_enabled() is False
        assert proc.get_fast_n_triggers() == 0

    def test_fast_layer_enabled(self):
        """FAST срабатывает на скачок."""
        proc = StreamingMagnus(
            n_sensors=2,
            degree=2,
            enable_fast=True,
            fast_alpha=0.1,
            fast_z_threshold=2.0,
        )

        assert proc.get_fast_enabled() is True

        for i in range(200):
            x = np.array([1.0 + 0.001 * np.sin(i), 1.0])
            proc.process(x)

        proc.process(np.array([10.0, 1.0]))

        assert proc.get_fast_n_triggers() > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
