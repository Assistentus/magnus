# -*- coding: utf-8 -*-
"""
magnus/streaming/visualizer.py
================================
Визуализация результатов Predictor.

Все графики сохраняются в указанную директорию.
"""

import numpy as np
from pathlib import Path
from typing import Optional, List

# Lazy import matplotlib
_plt = None

def _get_plt():
    global _plt
    if _plt is None:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        _plt = plt
    return _plt


# ================================================================
# ОСНОВНЫЕ ГРАФИКИ
# ================================================================

def plot_alerts_timeline(predictor_result,
                          loader,
                          output_path: str,
                          known_events: Optional[dict] = None):
    """
    График timeline алертов (FAST + SLOW).

    Args:
        predictor_result: PredictionResult
        loader: NPYConcatenatedLoader
        output_path: путь для сохранения PNG
        known_events: {source: 'event_name'} — известные события
    """
    plt = _get_plt()

    fig, ax = plt.subplots(figsize=(18, 8))

    # Точки алертов
    fast_t = [a.t for a in predictor_result.alerts if a.level == 'FAST']
    fast_score = [a.score for a in predictor_result.alerts if a.level == 'FAST']

    slow_t = [a.t for a in predictor_result.alerts if a.level == 'SLOW']
    slow_score = [a.score for a in predictor_result.alerts if a.level == 'SLOW']

    if fast_t:
        ax.scatter(fast_t, fast_score, c='red', s=120, marker='o',
                   edgecolors='darkred', linewidths=2,
                   label=f'FAST ({len(fast_t)})', zorder=5)
    if slow_t:
        ax.scatter(slow_t, slow_score, c='orange', s=120, marker='s',
                   edgecolors='darkorange', linewidths=2,
                   label=f'SLOW ({len(slow_t)})', zorder=5)

    # Известные события
    if known_events:
        boundaries = loader.file_boundaries
        for b in boundaries:
            src = b['source']
            if src in known_events:
                mid = (b['start'] + b['end']) // 2
                ax.axvline(x=mid, color='gray', alpha=0.3, linestyle='--')
                ax.text(mid, max(fast_score + slow_score) * 0.95 if (fast_score + slow_score) else 8,
                        known_events[src][:8],
                        rotation=90, fontsize=8, ha='right')

    ax.set_xlabel('Позиция в потоке (точки)')
    ax.set_ylabel('Score')
    ax.set_title(f'Timeline алертов Predictor '
                 f'(FAST={predictor_result.n_fast}, SLOW={predictor_result.n_slow})')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best')

    plt.tight_layout()
    plt.savefig(output_path, dpi=100)
    plt.close()

    print(f'📈 Timeline алертов: {output_path}')


def plot_alerts_by_source(predictor_result,
                           output_path: str,
                           known_events: Optional[dict] = None):
    """
    Гистограмма: срабатывания по файлам.
    """
    plt = _get_plt()

    sources = sorted(predictor_result.files_with_alerts.keys())

    fast_counts = [predictor_result.files_with_alerts[s].get('FAST', 0) for s in sources]
    slow_counts = [predictor_result.files_with_alerts[s].get('SLOW', 0) for s in sources]

    fig, ax = plt.subplots(figsize=(16, 6))

    x = np.arange(len(sources))
    width = 0.4

    ax.bar(x - width/2, fast_counts, width, label='FAST', color='red', alpha=0.7)
    ax.bar(x + width/2, slow_counts, width, label='SLOW', color='orange', alpha=0.7)

    # Известные события — звёздочка над столбцом
    if known_events:
        for i, src in enumerate(sources):
            if src in known_events:
                y = max(fast_counts[i] + slow_counts[i], 1) + 0.3
                ax.text(i, y, '★', ha='center', fontsize=14, color='darkred')

    ax.set_xticks(x)
    ax.set_xticklabels(sources, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('Количество алертов')
    ax.set_title('Алерты по файлам')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_path, dpi=100)
    plt.close()

    print(f'📈 Алерты по файлам: {output_path}')


def plot_sensors_degradation(loader,
                              sensors_to_plot: List[str],
                              output_path: str,
                              known_events: Optional[dict] = None):
    """
    Динамика ключевых датчиков по дням.

    Args:
        loader: NPYConcatenatedLoader
        sensors_to_plot: список имён датчиков
        output_path: путь для сохранения
        known_events: {source: 'event_name'}
    """
    plt = _get_plt()

    data = loader.get_all()
    boundaries = loader.file_boundaries

    sources = [b['source'] for b in boundaries]

    n_sensors = len(sensors_to_plot)
    fig, axes = plt.subplots(n_sensors, 1, figsize=(16, 3 * n_sensors))

    if n_sensors == 1:
        axes = [axes]

    for ax, sensor_name in zip(axes, sensors_to_plot):
        if sensor_name not in loader.sensors:
            ax.set_title(f'{sensor_name} (не найден)')
            continue

        idx = loader.sensors.index(sensor_name)

        means = []
        for b in boundaries:
            seg = data[b['start']:b['end'], idx]
            means.append(seg.mean())

        ax.plot(range(len(sources)), means, 'b-o', markersize=3)

        # Известные события
        if known_events:
            for i, src in enumerate(sources):
                if src in known_events:
                    ax.axvline(x=i, color='red', alpha=0.3, linestyle='--')

        ax.set_title(f'{sensor_name}')
        ax.set_ylabel('Среднее')
        ax.grid(True, alpha=0.3)

    # X-метки только на последнем
    step = max(1, len(sources) // 20)
    axes[-1].set_xticks(range(0, len(sources), step))
    axes[-1].set_xticklabels([sources[i] for i in range(0, len(sources), step)],
                              rotation=45, ha='right')

    plt.tight_layout()
    plt.savefig(output_path, dpi=100)
    plt.close()

    print(f'📈 Деградация датчиков: {output_path}')


def plot_sensor_around_event(loader,
                              sensor_name: str,
                              source: str,
                              output_path: str,
                              hours_before: int = 24,
                              hours_after: int = 24):
    """
    Значения одного датчика вокруг события.
    """
    plt = _get_plt()

    data = loader.get_all()

    # Границы
    b = None
    for bb in loader.file_boundaries:
        if bb['source'] == source:
            b = bb
            break

    if b is None:
        print(f'⚠️ Не найден источник {source}')
        return

    if sensor_name not in loader.sensors:
        print(f'⚠️ Не найден датчик {sensor_name}')
        return

    idx = loader.sensors.index(sensor_name)

    # Окно
    points_per_hour = 3600
    t_event = b['end'] - points_per_hour  # конец файла минус час
    t_start = max(0, t_event - hours_before * points_per_hour)
    t_end = min(data.shape[0], t_event + hours_after * points_per_hour)

    segment = data[t_start:t_end, idx]
    t_arr = np.arange(t_start, t_end)

    fig, ax = plt.subplots(figsize=(16, 5))
    ax.plot(t_arr, segment, 'b-', linewidth=0.5, alpha=0.7)
    ax.axvline(x=t_event, color='red', linestyle='--',
               label=f'Событие ({source})')

    ax.set_xlabel('Позиция')
    ax.set_ylabel(sensor_name)
    ax.set_title(f'{sensor_name} вокруг события {source}')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best')

    plt.tight_layout()
    plt.savefig(output_path, dpi=100)
    plt.close()

    print(f'📈 Датчик вокруг события: {output_path}')


# ================================================================
# ОБЩИЙ ОТЧЁТ
# ================================================================

def generate_full_report(predictor_result,
                          loader,
                          output_dir: str,
                          known_events: Optional[dict] = None,
                          sensors_to_plot: Optional[List[str]] = None):
    """
    Генерирует полный отчёт:
    - timeline алертов
    - алерты по файлам
    - динамика ключевых датчиков
    - JSON с алертами

    Args:
        predictor_result: PredictionResult
        loader: NPYConcatenatedLoader
        output_dir: директория для сохранения
        known_events: {source: 'event_name'}
        sensors_to_plot: список датчиков для графика динамики
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print()
    print('=' * 80)
    print('ГЕНЕРАЦИЯ ОТЧЁТА')
    print('=' * 80)
    print(f'Директория: {output_path}')
    print()

    # 1. Timeline
    plot_alerts_timeline(
        predictor_result, loader,
        str(output_path / 'timeline_alerts.png'),
        known_events=known_events,
    )

    # 2. Алерты по файлам
    plot_alerts_by_source(
        predictor_result,
        str(output_path / 'alerts_by_source.png'),
        known_events=known_events,
    )

    # 3. Динамика датчиков
    if sensors_to_plot is None:
        sensors_to_plot = ['V red', 'V gen', 'Pgaza na vihod',
                            't gaz na vih iz GTD', 'N tk']

    plot_sensors_degradation(
        loader, sensors_to_plot,
        str(output_path / 'sensors_degradation.png'),
        known_events=known_events,
    )

    # 4. JSON
    predictor_result.to_json(str(output_path / 'alerts.json'))

    print()
    print(f'✅ Отчёт готов: {output_path}')
    print()