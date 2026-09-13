# benchmarks/streaming_benchmark.py
# ===================================================================
# Бенчмарк потоковой обработки.
# ===================================================================

import time
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from magnus.streaming import StreamingMagnus


def benchmark(n_points: int, n_sensors: int = 7):
    print(f"\n{'='*60}")
    print(f"Бенчмарк: {n_points:,} точек, {n_sensors} датчиков")
    print(f"{'='*60}")

    proc = StreamingMagnus(
        n_sensors=n_sensors,
        alpha=0.05,
        n_sigma=1.5,
        min_count=2,
        degree=3,
    )

    # Синтетические данные
    np.random.seed(42)

    data = np.cumsum(np.random.randn(n_points, n_sensors) * 0.01, axis=0)
    data += np.random.randn(n_points, n_sensors) * 0.5

    # Обработка
    print(f"\nТочка за точкой...")
    start = time.time()

    for x in data:
        proc.process(x)

    elapsed = time.time() - start

    print(f"  Время:      {elapsed:.3f} сек")
    print(f"  Скорость:   {n_points / elapsed:.0f} точек/сек")
    print(f"  Ранг:       {proc.rank}")
    print(f"  Состояний:  {proc.n_states}")
    print(f"  Переходов:  {proc.n_transitions}")


if __name__ == "__main__":
    benchmark(10_000)
    benchmark(86_411)  # 1 день данных КАДВИ
    benchmark(1_000_000)