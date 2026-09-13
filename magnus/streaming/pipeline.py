# -*- coding: utf-8 -*-
"""
magnus/streaming/pipeline.py
=============================
УНИВЕРСАЛЬНЫЙ потоковый процессор Magnus.

Поддерживает:
- batch (файлы, по одному)
- batch concatenated (все файлы как единый поток)
- batch concatenated NPY (из единого .npy через mmap) — самый быстрый
- stream (реальное время)
- любой degree (1..N) и path_length
- оконный режим (window_size > 0) с нахлёстом (overlap)
- отпечатки окон с ленивой привязкой к источнику по позиции t
"""

import os
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Callable, Iterator, Any, Tuple
from dataclasses import dataclass, field


# ================================================================
# ОТПЕЧАТОК ОКНА
# ================================================================

@dataclass
class WindowFingerprint:
    """
    Отпечаток закрытого окна.

    Привязка к источнику делается ЛЕНИВО через
    ProcessingResult.source_for_window(fp).

    В самом отпечатке source не хранится — только абсолютные позиции.
    """
    t_start: int
    t_end: int
    n_points: int
    rank: int
    n_states: int
    n_words: int
    n_transitions: int
    is_partial: bool = False
    is_tail: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            't_start': self.t_start,
            't_end': self.t_end,
            'n_points': self.n_points,
            'rank': self.rank,
            'n_states': self.n_states,
            'n_words': self.n_words,
            'n_transitions': self.n_transitions,
            'is_partial': self.is_partial,
            'is_tail': self.is_tail,
        }

    @property
    def rank_per_1k(self) -> float:
        """Rank на 1000 точек — сравнимая метрика для окон разного размера."""
        if self.n_points == 0:
            return 0.0
        return 1000.0 * self.rank / self.n_points

    @property
    def center(self) -> int:
        """Центр окна — используется для привязки к источнику."""
        return (self.t_start + self.t_end) // 2


# ================================================================
# РЕЗУЛЬТАТЫ
# ================================================================

@dataclass
class DayResult:
    """Результат обработки одного источника."""
    source: str
    n_points: int

    rank_start: int
    rank_end: int
    delta_rank: int

    n_states_start: int
    n_states_end: int
    delta_states: int

    n_transitions_start: int
    n_transitions_end: int
    delta_transitions: int

    n_words_start: int = 0
    n_words_end: int = 0
    delta_words: int = 0

    n_windows_closed: int = 0

    ranks_per_point: Optional[np.ndarray] = None
    rank_increases: Optional[np.ndarray] = None
    growth_times: List[int] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            'source': self.source,
            'n_points': self.n_points,
            'rank_start': self.rank_start,
            'rank_end': self.rank_end,
            'delta_rank': self.delta_rank,
            'n_states_start': self.n_states_start,
            'n_states_end': self.n_states_end,
            'delta_states': self.delta_states,
            'n_transitions_start': self.n_transitions_start,
            'n_transitions_end': self.n_transitions_end,
            'delta_transitions': self.delta_transitions,
            'n_words_start': self.n_words_start,
            'n_words_end': self.n_words_end,
            'delta_words': self.delta_words,
            'n_windows_closed': self.n_windows_closed,
        }

    def has_details(self) -> bool:
        return self.ranks_per_point is not None


@dataclass
class ProcessingResult:
    """Результат обработки всего потока."""
    days: List[DayResult]
    total_points: int
    total_rank: int
    total_states: int
    total_transitions: int
    total_words: int
    sensors_used: List[str]

    degree: int = 3
    path_length: int = 4
    window_size: int = 0
    overlap: int = 0
    mode: str = "sequential"

    window_fingerprints: List[WindowFingerprint] = field(default_factory=list)

    # Границы файлов (для concatenated)
    file_boundaries: List[Tuple[int, int, str]] = field(default_factory=list)

    # ============================================================
    # ЭКСПОРТ
    # ============================================================

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([d.as_dict() for d in self.days])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'days': [d.as_dict() for d in self.days],
            'total_points': self.total_points,
            'total_rank': self.total_rank,
            'total_states': self.total_states,
            'total_transitions': self.total_transitions,
            'total_words': self.total_words,
            'sensors_used': self.sensors_used,
            'degree': self.degree,
            'path_length': self.path_length,
            'window_size': self.window_size,
            'overlap': self.overlap,
            'mode': self.mode,
            'n_windows': len(self.window_fingerprints),
            'window_fingerprints': [fp.as_dict() for fp in self.window_fingerprints],
            'file_boundaries': [
                {'start': s, 'end': e, 'source': src}
                for s, e, src in self.file_boundaries
            ],
        }

    def to_json(self, output_path: str):
        """Сохранить результат в JSON."""
        import json
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"💾 Результат сохранён: {output_path}")

    # ============================================================
    # РЕЗОЛВЛЕНИЕ SOURCE ПО ПОЗИЦИИ
    # ============================================================

    def source_at(self, t: int) -> Optional[str]:
        """
        Определяет source по абсолютной позиции t (бинарный поиск).
        """
        if not self.file_boundaries:
            return None

        lo, hi = 0, len(self.file_boundaries) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            start, end, src = self.file_boundaries[mid]
            if t < start:
                hi = mid - 1
            elif t >= end:
                lo = mid + 1
            else:
                return src
        return None

    def source_for_window(self, fp: WindowFingerprint) -> Optional[str]:
        """Определяет source для окна (по центру)."""
        return self.source_at(fp.center)

    def source_range(self, start: int, end: int) -> List[str]:
        """Все sources в диапазоне [start, end)."""
        sources = []
        for s, e, src in self.file_boundaries:
            if e <= start:
                continue
            if s >= end:
                break
            sources.append(src)
        return sources

    # ============================================================
    # АНАЛИЗ
    # ============================================================

    def get_day(self, source: str) -> Optional[DayResult]:
        for d in self.days:
            if d.source == source:
                return d
        return None

    def get_days_with_details(self) -> List[DayResult]:
        return [d for d in self.days if d.has_details()]

    def windows_dataframe(self) -> pd.DataFrame:
        if not self.window_fingerprints:
            return pd.DataFrame()
        rows = []
        for fp in self.window_fingerprints:
            d = fp.as_dict()
            d['source'] = self.source_for_window(fp)
            d['rank_per_1k'] = fp.rank_per_1k
            rows.append(d)
        return pd.DataFrame(rows)

    def windows_by_source(self) -> Dict[str, List[WindowFingerprint]]:
        """Группирует окна по источнику (через source_for_window)."""
        result: Dict[str, List[WindowFingerprint]] = {}
        for fp in self.window_fingerprints:
            key = self.source_for_window(fp) or "unknown"
            result.setdefault(key, []).append(fp)
        return result

    def summary(self) -> str:
        lines = [
            f"Режим:             {self.mode}",
            f"Источников:        {len(self.days)}",
            f"Всего точек:       {self.total_points:,}",
            f"Финальный ранг:    {self.total_rank:,}",
            f"Состояний:         {self.total_states:,}",
            f"Переходов:         {self.total_transitions:,}",
            f"Слов (путей):      {self.total_words:,}",
            f"Датчиков:          {len(self.sensors_used)}",
            f"degree:            {self.degree}",
            f"path_length:       {self.path_length}",
            f"window_size:       {self.window_size}",
            f"overlap:           {self.overlap}",
        ]
        if self.window_fingerprints:
            lines.append(f"Окон закрыто:      {len(self.window_fingerprints)}")
            n_partial = sum(1 for fp in self.window_fingerprints if fp.is_partial)
            n_tail = sum(1 for fp in self.window_fingerprints if fp.is_tail)
            if n_partial:
                lines.append(f"  из них неполных: {n_partial}")
            if n_tail:
                lines.append(f"  из них хвостовых: {n_tail}")
        return "\n".join(lines)

    # ============================================================
    # ДЕТЕКЦИЯ АНОМАЛИЙ
    # ============================================================

    def detect_anomalies(self,
                          window_lookback: int = 10,
                          threshold_pct: float = 25.0,
                          exclude_partial: bool = True) -> List[Dict[str, Any]]:
        """
        Автоматическая детекция аномалий по оконным отпечаткам.

        Идея: если rank окна упал более чем на threshold_pct%
        от скользящего среднего — это аномалия.
        """
        fps = self.window_fingerprints
        if exclude_partial:
            fps = [fp for fp in fps if not fp.is_partial]

        if len(fps) < window_lookback + 1:
            return []

        anomalies = []
        for i in range(window_lookback, len(fps)):
            recent = fps[i - window_lookback:i]
            avg = sum(fp.rank for fp in recent) / window_lookback
            actual = fps[i].rank

            if avg > 0 and actual < avg * (1 - threshold_pct / 100):
                anomalies.append({
                    'window': fps[i],
                    't_start': fps[i].t_start,
                    't_end': fps[i].t_end,
                    'source': self.source_for_window(fps[i]),
                    'expected': avg,
                    'actual': actual,
                    'drop_pct': 100 * (1 - actual / avg),
                })

        return anomalies

    def print_anomalies(self, threshold_pct: float = 25.0,
                         window_lookback: int = 10):
        """Печатает аномалии в удобном виде."""
        anomalies = self.detect_anomalies(
            window_lookback=window_lookback,
            threshold_pct=threshold_pct,
        )

        print()
        print("=" * 80)
        print(f"АВТОМАТИЧЕСКАЯ ДЕТЕКЦИЯ АНОМАЛИЙ (порог: -{threshold_pct:.0f}%)")
        print("=" * 80)

        if not anomalies:
            print("✅ Аномалий не обнаружено")
            return

        print(f"🚨 ОБНАРУЖЕНО АНОМАЛИЙ: {len(anomalies)}")
        print()
        print(f"{'t_start':>10} {'Источник':<12} {'Ожидалось':>10} "
              f"{'Факт':>8} {'Падение':>10}")
        print("-" * 60)

        for a in anomalies:
            print(f"{a['t_start']:>10} {a['source'] or '':<12} "
                  f"{a['expected']:>10.0f} {a['actual']:>8,} "
                  f"{a['drop_pct']:>9.1f}%")

    def print_events_comparison(self,
                                  events_map: Dict[str, str],
                                  threshold_pct: float = 25.0):
        """
        Сравнение окон с известными событиями.

        Окна привязываются к источнику через source_for_window
        (по центру окна).
        """
        fps = [fp for fp in self.window_fingerprints if not fp.is_partial]
        if not fps:
            return

        avg_rank = sum(fp.rank for fp in fps) / len(fps)

        print()
        print("=" * 80)
        print(f"СРАВНЕНИЕ С ИЗВЕСТНЫМИ СОБЫТИЯМИ (avg_rank={avg_rank:.0f})")
        print("=" * 80)
        print(f"{'Источник':<12} {'Событие':<18} {'Окон':>6} "
              f"{'Мин rank':>10} {'Отклон.':>10} {'Статус':>10}")
        print("-" * 80)

        # Группируем окна по источнику
        by_source = self.windows_by_source()

        for src, event in events_map.items():
            src_fps = by_source.get(src, [])

            if not src_fps:
                print(f"{src:<12} {event:<18} {'—':>6} {'—':>10} {'—':>10} "
                      f"{'НЕТ ОКОН':>10}")
                continue

            min_rank = min(fp.rank for fp in src_fps)
            deviation_pct = 100 * (avg_rank - min_rank) / avg_rank

            if deviation_pct >= 50:
                status = "🚨 КРИТ"
            elif deviation_pct >= threshold_pct:
                status = "⚠️ АЛЕРТ"
            else:
                status = "✓ норма"

            print(f"{src:<12} {event:<18} {len(src_fps):>6} "
                  f"{min_rank:>10,} {deviation_pct:>9.1f}% "
                  f"{status:>10}")

    def plot_windows(self,
                      output_path: str = "/tmp/rank_windows.png",
                      threshold_pct: float = 25.0):
        """График rank по окнам с отмеченными аномалиями."""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            print("⚠️ matplotlib не установлен. pip install matplotlib")
            return

        fps_all = self.window_fingerprints
        fps = [fp for fp in fps_all if not fp.is_partial]

        if not fps:
            print("⚠️ Нет полных окон для визуализации")
            return

        t = [fp.t_start for fp in fps]
        rank = [fp.rank for fp in fps]

        fig, ax = plt.subplots(figsize=(16, 7))
        ax.plot(t, rank, 'b-', linewidth=0.8, label='rank', alpha=0.7)

        # Скользящее среднее
        if len(rank) >= 10:
            ma = np.convolve(rank, np.ones(10) / 10, mode='valid')
            ax.plot(t[9:], ma, 'g--', alpha=0.7,
                    label='MA(10)', linewidth=1.5)

        # Аномалии
        anomalies = self.detect_anomalies(threshold_pct=threshold_pct)
        if anomalies:
            a_t = [a['t_start'] for a in anomalies]
            a_r = [a['actual'] for a in anomalies]
            ax.scatter(a_t, a_r, c='red', s=80, zorder=5,
                       label=f'Аномалии (n={len(anomalies)})',
                       edgecolors='darkred', linewidths=1.5)

        ax.set_xlabel('Точки (позиция в потоке)')
        ax.set_ylabel('Rank')
        ax.set_title(
            f'Динамика rank — {len(fps)} окон '
            f'(degree={self.degree}, window={self.window_size}, '
            f'overlap={self.overlap})'
        )
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best')
        plt.tight_layout()
        plt.savefig(output_path, dpi=100)
        plt.close()

        print(f"📈 График сохранён: {output_path}")


# ================================================================
# PIPELINE
# ================================================================

class StreamingPipeline:
    """
    Универсальный потоковый процессор Magnus.
    """

    def __init__(self,
                 sensors: List[str],
                 loader: Optional[Callable[[str, List[str]], Optional[np.ndarray]]] = None,
                 alpha: float = 0.05,
                 n_sigma: float = 1.5,
                 min_count: int = 2,
                 degree: int = 3,
                 path_length: int = 0,
                 window_size: int = 0,
                 overlap: int = 0,
                 p: int = 1_000_000_007):
        self._validate_sensors(sensors)

        try:
            from fr_rank_rs import StreamingMagnus
        except ImportError:
            raise ImportError(
                "fr_rank_rs не собран. "
                "Запустите: python setup.py build_ext --inplace"
            )

        if not (0.0 < alpha <= 1.0):
            raise ValueError(f"alpha={alpha} должен быть в (0, 1]")
        if n_sigma <= 0:
            raise ValueError(f"n_sigma={n_sigma} должен быть > 0")
        if min_count < 1:
            raise ValueError(f"min_count={min_count} должен быть >= 1")
        if degree < 1:
            raise ValueError(f"degree={degree} должен быть >= 1")
        if window_size < 0:
            raise ValueError(f"window_size={window_size} должен быть >= 0")
        if overlap < 0:
            raise ValueError(f"overlap={overlap} должен быть >= 0")
        if window_size > 0 and overlap >= window_size:
            raise ValueError(
                f"overlap ({overlap}) должен быть < window_size ({window_size})"
            )

        if path_length == 0:
            path_length = degree + 1
        if path_length < degree + 1:
            path_length = degree + 1

        self.requested_sensors = list(sensors)
        self.loader = loader
        self.alpha = alpha
        self.n_sigma = n_sigma
        self.min_count = min_count
        self.degree = degree
        self.path_length = path_length
        self.window_size = window_size
        self.overlap = overlap
        self.p = p

        self._proc_class = StreamingMagnus
        self.proc = None
        self.sensors_used: Optional[List[str]] = None
        self.n_sensors: Optional[int] = None

        self.global_t = 0
        self.prev_rank = 0
        self.prev_states = 0
        self.prev_transitions = 0
        self.prev_words = 0
        self.prev_windows_closed = 0

        self._all_window_fingerprints: List[WindowFingerprint] = []
        self._last_fp_index = 0

    # ============================================================
    # ВАЛИДАЦИЯ
    # ============================================================

    @staticmethod
    def _validate_sensors(sensors: List[str]) -> None:
        if sensors is None:
            raise ValueError("Параметр 'sensors' обязателен")
        if not isinstance(sensors, (list, tuple)):
            raise ValueError(
                f"Параметр 'sensors' должен быть списком, "
                f"получено: {type(sensors).__name__}"
            )
        if len(sensors) == 0:
            raise ValueError("Параметр 'sensors' пуст")
        for s in sensors:
            if not isinstance(s, str) or not s.strip():
                raise ValueError(f"Недопустимое имя датчика: {s!r}")

    @staticmethod
    def _validate_loader(loader: Callable) -> None:
        if loader is None or not callable(loader):
            raise ValueError(
                "Для process_files() требуется 'loader'. "
                "Передайте функцию: loader(filepath, sensors) → np.ndarray"
            )

    # ============================================================
    # ИНИЦИАЛИЗАЦИЯ
    # ============================================================

    def _init_processor(self, n_sensors: int) -> None:
        if self.proc is None:
            self.proc = self._proc_class(
                n_sensors=n_sensors,
                alpha=self.alpha,
                n_sigma=self.n_sigma,
                min_count=self.min_count,
                degree=self.degree,
                path_length=self.path_length,
                window_size=self.window_size,
                overlap=self.overlap,
            )
            self.n_sensors = n_sensors

    def _check_n_sensors(self, n_actual: int, source: str) -> bool:
        if self.n_sensors is None:
            return True
        if n_actual != self.n_sensors:
            print(f"  ⚠️ {source}: число датчиков не совпадает "
                  f"({n_actual} vs {self.n_sensors})")
            return False
        return True

    def _collect_new_fingerprints(self) -> int:
        """
        Забирает новые отпечатки окон из Rust.

        НЕ привязывает к источнику — привязка делается лениво
        через ProcessingResult.source_for_window(fp).
        """
        if self.proc is None or self.window_size == 0:
            return 0

        all_fps = self.proc.get_window_fingerprints()
        n_total = len(all_fps)

        if n_total <= self._last_fp_index:
            return 0

        for fp_tuple in all_fps[self._last_fp_index:]:
            # tuple: (t_start, t_end, n_points, rank, n_states,
            #         n_words, n_transitions, is_partial, is_tail)
            (t_start, t_end, n_pts, rank, n_states,
             n_words, n_trans, is_partial, is_tail) = fp_tuple

            self._all_window_fingerprints.append(WindowFingerprint(
                t_start=int(t_start),
                t_end=int(t_end),
                n_points=int(n_pts),
                rank=int(rank),
                n_states=int(n_states),
                n_words=int(n_words),
                n_transitions=int(n_trans),
                is_partial=bool(is_partial),
                is_tail=bool(is_tail),
            ))

        n_new = n_total - self._last_fp_index
        self._last_fp_index = n_total
        return n_new

    # ============================================================
    # ОБРАБОТКА ФАЙЛОВ (последовательно)
    # ============================================================

    def process_files(self,
                       filepaths: List[str],
                       sources: Optional[List[str]] = None,
                       detail_sources: Optional[List[str]] = None,
                       verbose: bool = True) -> ProcessingResult:
        self._validate_loader(self.loader)

        if not filepaths:
            return self._empty_result(mode="sequential")

        if sources is None:
            sources = [os.path.basename(fp).rsplit('.', 1)[0]
                       for fp in filepaths]

        if detail_sources is None:
            detail_sources = []

        if len(sources) != len(filepaths):
            raise ValueError(
                f"Длина sources ({len(sources)}) != "
                f"длина filepaths ({len(filepaths)})"
            )

        if verbose:
            print(f"\n{'Источник':<20} {'Точек':>10} {'Δ Ранг':>8} "
                  f"{'Ранг':>10} {'Δ Сост':>8} {'Δ Перех':>10} "
                  f"{'Окон':>6}")
            print("-"*85)

        days = []

        for filepath, source in zip(filepaths, sources):
            detail = source in detail_sources
            result = self._process_single_file(filepath, source, detail=detail)

            if result is None:
                if verbose:
                    print(f"{source:<20} ПРОПУЩЕН")
                continue

            days.append(result)

            if verbose:
                print(f"{source:<20} {result.n_points:>10,} "
                      f"{result.delta_rank:>+8} {result.rank_end:>10} "
                      f"{result.delta_states:>+8} "
                      f"{result.delta_transitions:>+10} "
                      f"{result.n_windows_closed:>6}")

        return self._build_result(days, mode="sequential")

    def _process_single_file(self,
                              filepath: str,
                              source: str,
                              detail: bool = False) -> Optional[DayResult]:
        data = self.loader(filepath, self.requested_sensors)
        if data is None:
            return None
        if data.ndim != 2:
            print(f"  ⚠️ {source}: данные не 2D (shape={data.shape})")
            return None

        n_points, n_actual = data.shape
        if n_actual == 0 or n_points == 0:
            return None

        if self.proc is None:
            self._init_processor(n_actual)
            self.sensors_used = self.requested_sensors[:n_actual]
        elif not self._check_n_sensors(n_actual, source):
            return None

        data = np.ascontiguousarray(data, dtype=np.float64)
        flat = data.flatten()

        return self._process_array(flat, n_points, source, detail=detail)

    # ============================================================
    # CONCATENATED: все файлы как единый поток (через loader)
    # ============================================================

    def process_concatenated(self,
                              filepaths: List[str],
                              sources: Optional[List[str]] = None,
                              verbose: bool = True) -> ProcessingResult:
        """
        Обрабатывает ВСЕ файлы как единый непрерывный поток точек.

        Окна режутся равномерно по всему потоку, не привязаны к границам.
        В конце потока хвостовое окно закрывается принудительно (flush).

        Привязка окон к источникам — ленивая, через source_for_window.
        """
        self._validate_loader(self.loader)

        if not filepaths:
            return self._empty_result(mode="concatenated")

        if sources is None:
            sources = [os.path.basename(fp).rsplit('.', 1)[0]
                       for fp in filepaths]

        if len(sources) != len(filepaths):
            raise ValueError(
                f"Длина sources ({len(sources)}) != "
                f"длина filepaths ({len(filepaths)})"
            )

        # 1. Загрузка + конкатенация
        all_data = []
        file_boundaries: List[Tuple[int, int, str]] = []
        total_loaded = 0

        if verbose:
            print(f"📂 Загрузка {len(filepaths)} файлов...")

        for i, (fp, src) in enumerate(zip(filepaths, sources)):
            data = self.loader(fp, self.requested_sensors)
            if data is None:
                if verbose:
                    print(f"  ⚠️ [{i+1}/{len(filepaths)}] {src}: ПРОПУЩЕН")
                continue

            if data.ndim != 2:
                if verbose:
                    print(f"  ⚠️ [{i+1}/{len(filepaths)}] {src}: не 2D")
                continue

            n_pts, n_actual = data.shape
            if n_pts == 0 or n_actual == 0:
                continue

            data = np.ascontiguousarray(data, dtype=np.float64)

            if self.n_sensors is None and i == 0:
                self._init_processor(n_actual)
                self.sensors_used = self.requested_sensors[:n_actual]
            elif n_actual != self.n_sensors:
                if verbose:
                    print(f"  ⚠️ [{i+1}/{len(filepaths)}] {src}: "
                          f"n_sensors={n_actual} vs {self.n_sensors}, пропуск")
                continue

            all_data.append(data)
            file_boundaries.append((total_loaded, total_loaded + n_pts, src))
            total_loaded += n_pts

        if not all_data:
            return self._empty_result(mode="concatenated")

        # 2. Объединение
        combined = np.vstack(all_data)
        n_points, n_sensors = combined.shape

        if verbose:
            print(f"📂 Сращено: {len(all_data)} файлов → {n_points:,} точек")
            print(f"📂 window_size={self.window_size}, "
                  f"overlap={self.overlap}")

        # 3. Обработка как единого потока
        flat = combined.flatten()

        for i in range(n_points):
            start = i * n_sensors
            end = start + n_sensors
            self.proc.process(flat[start:end])
            self.global_t += 1

        # 4. Flush хвостового окна
        flushed = False
        if self.window_size > 0:
            flushed = self.proc.flush()
            if verbose and flushed:
                print(f"📂 Хвостовое окно закрыто (flush)")

        # 5. Забираем отпечатки
        self._collect_new_fingerprints()

        # 6. DayResult по границам
        days = self._days_from_boundaries(file_boundaries, n_points)

        if verbose:
            print(f"\n{'Источник':<20} {'Точек':>10} {'Окон (внутри)':>15}")
            print("-"*50)
            for d in days:
                print(f"{d.source:<20} {d.n_points:>10,} "
                      f"{d.n_windows_closed:>15}")

        return self._build_result(
            days,
            mode="concatenated",
            file_boundaries=file_boundaries,
        )

    # ============================================================
    # CONCATENATED NPY: максимально быстрый путь
    # ============================================================

    def process_concatenated_npy(self,
                                   loader,
                                   verbose: bool = True) -> ProcessingResult:
        """
        Максимально быстрая обработка из NPYConcatenatedLoader.

        Не использует pandas. Загружает данные через mmap.
        Привязка окон к источникам — ленивая, через source_for_window.
        """
        # Проверка интерфейса loader
        if not hasattr(loader, 'get_all'):
            raise ValueError(
                "loader должен быть NPYConcatenatedLoader "
                "(или совместим с интерфейсом: get_all, boundaries, "
                "source_at, n_sensors, sensors)"
            )

        # Инициализация
        self._init_processor(loader.n_sensors)
        self.sensors_used = loader.sensors[:loader.n_sensors]

        # Данные (mmap-view)
        data = loader.get_all()
        n_points = data.shape[0]

        if verbose:
            print(f"📂 NPY загружен: {n_points:,} точек × "
                  f"{loader.n_sensors} датчиков")
            print(f"📂 Sources: {len(loader.file_boundaries)} файлов")
            print(f"📂 window_size={self.window_size}, "
                  f"overlap={self.overlap}")

        # Плоский массив
        flat = np.ascontiguousarray(data).flatten()

        # Обработка поточечно
        for i in range(n_points):
            start = i * loader.n_sensors
            end = start + loader.n_sensors
            self.proc.process(flat[start:end])
            self.global_t += 1

        # Flush хвостового окна
        flushed = False
        if self.window_size > 0:
            flushed = self.proc.flush()
            if verbose and flushed:
                print(f"📂 Хвостовое окно закрыто (flush)")

        # Забираем отпечатки
        self._collect_new_fingerprints()

        # Границы
        boundaries = loader.boundaries()
        days = self._days_from_boundaries(boundaries, n_points)

        if verbose:
            print(f"\n{'Источник':<20} {'Точек':>10} {'Окон (внутри)':>15}")
            print("-"*50)
            for d in days:
                print(f"{d.source:<20} {d.n_points:>10,} "
                      f"{d.n_windows_closed:>15}")

        return self._build_result(
            days,
            mode="concatenated_npy",
            file_boundaries=boundaries,
        )

    def _days_from_boundaries(self,
                               file_boundaries: List[Tuple[int, int, str]],
                               total_points: int) -> List[DayResult]:
        """
        Формирует DayResult для каждого файла на основе границ.

        n_windows_closed считает окна, центр которых попадает в файл.
        """
        days = []

        for idx, (start, end, src) in enumerate(file_boundaries):
            n_points = end - start

            # Окна, центр которых попадает в диапазон [start, end)
            n_windows = 0
            for fp in self._all_window_fingerprints:
                center = (fp.t_start + fp.t_end) // 2
                if start <= center < end:
                    n_windows += 1

            days.append(DayResult(
                source=src,
                n_points=n_points,
                rank_start=0,
                rank_end=0,
                delta_rank=0,
                n_states_start=0,
                n_states_end=0,
                delta_states=0,
                n_transitions_start=0,
                n_transitions_end=0,
                delta_transitions=0,
                n_words_start=0,
                n_words_end=0,
                delta_words=0,
                n_windows_closed=n_windows,
            ))

        return days

    # ============================================================
    # ВНУТРЕННЯЯ ОБРАБОТКА
    # ============================================================

    def _process_array(self,
                        flat: np.ndarray,
                        n_points: int,
                        source: str,
                        detail: bool = False) -> DayResult:
        n_sensors = self.n_sensors

        rank_start = self.prev_rank
        states_start = self.prev_states
        transitions_start = self.prev_transitions
        words_start = self.prev_words
        windows_closed_start = self.prev_windows_closed

        if detail:
            ranks_per_point = np.zeros(n_points, dtype=np.int64)
            rank_increases = np.zeros(n_points, dtype=np.int32)
        else:
            ranks_per_point = None
            rank_increases = None

        growth_times: List[int] = []

        for i in range(n_points):
            start = i * n_sensors
            end = start + n_sensors
            point = flat[start:end]

            result = self.proc.process(point)
            self.global_t += 1

            if detail:
                ranks_per_point[i] = result['rank']
                rank_increases[i] = 1 if result['rank_increased'] else 0

            if result['rank_increased']:
                growth_times.append(i)

        self._collect_new_fingerprints()

        rank_end = self.proc.get_rank()
        states_end = self.proc.get_n_states()
        transitions_end = self.proc.get_n_transitions()
        words_end = self.proc.get_n_words()
        windows_closed_end = self.proc.get_n_windows_closed()

        n_windows_in_file = windows_closed_end - windows_closed_start

        day_result = DayResult(
            source=source,
            n_points=n_points,
            rank_start=rank_start,
            rank_end=rank_end,
            delta_rank=rank_end - rank_start,
            n_states_start=states_start,
            n_states_end=states_end,
            delta_states=states_end - states_start,
            n_transitions_start=transitions_start,
            n_transitions_end=transitions_end,
            delta_transitions=transitions_end - transitions_start,
            n_words_start=words_start,
            n_words_end=words_end,
            delta_words=words_end - words_start,
            n_windows_closed=n_windows_in_file,
            ranks_per_point=ranks_per_point,
            rank_increases=rank_increases,
            growth_times=growth_times,
        )

        self.prev_rank = rank_end
        self.prev_states = states_end
        self.prev_transitions = transitions_end
        self.prev_words = words_end
        self.prev_windows_closed = windows_closed_end

        return day_result

    # ============================================================
    # STREAM
    # ============================================================

    def process_source(self, source, verbose: bool = False) -> ProcessingResult:
        days_data: Dict[str, DayResult] = {}
        current_source: Optional[str] = None
        current_results: List[Dict[str, Any]] = []

        for item in source:
            src = item.get('source', 'unknown')
            values = item.get('values')
            if values is None:
                continue
            values = np.ascontiguousarray(values, dtype=np.float64)

            if self.proc is None:
                n_actual = len(values)
                self._init_processor(n_actual)
                self.sensors_used = self.requested_sensors[:n_actual]

            if current_source != src:
                if current_source is not None and current_results:
                    self._collect_new_fingerprints()
                    days_data[current_source] = self._finalize_stream_day(
                        current_source, current_results
                    )
                    if verbose:
                        d = days_data[current_source]
                        print(f"  {current_source}: rank={d.rank_end}")
                current_source = src
                current_results = []

            result = self.proc.process(values)
            self.global_t += 1
            current_results.append(result)

        if current_source is not None and current_results:
            self._collect_new_fingerprints()
            days_data[current_source] = self._finalize_stream_day(
                current_source, current_results
            )

        return self._build_result(list(days_data.values()), mode="stream")

    def process_stream(self,
                        stream: Iterator[Dict[str, Any]],
                        source_key: str = 'source',
                        values_key: str = 'values') -> ProcessingResult:
        days_data: Dict[str, DayResult] = {}
        current_source: Optional[str] = None
        current_results: List[Dict[str, Any]] = []

        for item in stream:
            src = item.get(source_key, 'unknown')
            values = item.get(values_key)
            if values is None:
                continue
            values = np.ascontiguousarray(values, dtype=np.float64)

            if self.proc is None:
                n_actual = len(values)
                self._init_processor(n_actual)
                self.sensors_used = self.requested_sensors[:n_actual]

            if current_source != src:
                if current_source is not None and current_results:
                    self._collect_new_fingerprints()
                    days_data[current_source] = self._finalize_stream_day(
                        current_source, current_results
                    )
                current_source = src
                current_results = []

            result = self.proc.process(values)
            self.global_t += 1
            current_results.append(result)

        if current_source is not None and current_results:
            self._collect_new_fingerprints()
            days_data[current_source] = self._finalize_stream_day(
                current_source, current_results
            )

        return self._build_result(list(days_data.values()), mode="stream")

    def _finalize_stream_day(self,
                              source: str,
                              results: List[Dict[str, Any]]) -> DayResult:
        valid = [r for r in results if r is not None]
        if not valid:
            return DayResult(
                source=source, n_points=0,
                rank_start=self.prev_rank, rank_end=self.prev_rank,
                delta_rank=0,
                n_states_start=self.prev_states, n_states_end=self.prev_states,
                delta_states=0,
                n_transitions_start=self.prev_transitions,
                n_transitions_end=self.prev_transitions,
                delta_transitions=0,
                n_words_start=self.prev_words, n_words_end=self.prev_words,
                delta_words=0,
            )

        rank_start = valid[0]['rank']
        rank_end = valid[-1]['rank']
        states_start = valid[0]['n_states']
        states_end = valid[-1]['n_states']
        transitions_start = valid[0]['n_transitions']
        transitions_end = valid[-1]['n_transitions']
        words_start = valid[0].get('n_words', 0)
        words_end = valid[-1].get('n_words', 0)

        self.prev_rank = rank_end
        self.prev_states = states_end
        self.prev_transitions = transitions_end
        self.prev_words = words_end

        return DayResult(
            source=source,
            n_points=len(valid),
            rank_start=rank_start, rank_end=rank_end,
            delta_rank=rank_end - rank_start,
            n_states_start=states_start, n_states_end=states_end,
            delta_states=states_end - states_start,
            n_transitions_start=transitions_start,
            n_transitions_end=transitions_end,
            delta_transitions=transitions_end - transitions_start,
            n_words_start=words_start, n_words_end=words_end,
            delta_words=words_end - words_start,
        )

    # ============================================================
    # РЕЗУЛЬТАТ
    # ============================================================

    def _build_result(self,
                       days: List[DayResult],
                       mode: str = "sequential",
                       file_boundaries: Optional[List[Tuple[int, int, str]]] = None
                       ) -> ProcessingResult:
        return ProcessingResult(
            days=days,
            total_points=self.global_t,
            total_rank=self.proc.get_rank() if self.proc else 0,
            total_states=self.proc.get_n_states() if self.proc else 0,
            total_transitions=self.proc.get_n_transitions() if self.proc else 0,
            total_words=self.proc.get_n_words() if self.proc else 0,
            sensors_used=self.sensors_used or [],
            degree=self.degree,
            path_length=self.path_length,
            window_size=self.window_size,
            overlap=self.overlap,
            mode=mode,
            window_fingerprints=list(self._all_window_fingerprints),
            file_boundaries=file_boundaries or [],
        )

    def _empty_result(self, mode: str = "sequential") -> ProcessingResult:
        return ProcessingResult(
            days=[],
            total_points=0,
            total_rank=0,
            total_states=0,
            total_transitions=0,
            total_words=0,
            sensors_used=[],
            degree=self.degree,
            path_length=self.path_length,
            window_size=self.window_size,
            overlap=self.overlap,
            mode=mode,
        )

    # ============================================================
    # СБРОС
    # ============================================================

    def reset(self) -> None:
        if self.proc:
            self.proc.reset()
        self.global_t = 0
        self.prev_rank = 0
        self.prev_states = 0
        self.prev_transitions = 0
        self.prev_words = 0
        self.prev_windows_closed = 0
        self._all_window_fingerprints.clear()
        self._last_fp_index = 0

    # ============================================================
    # МЕТРИКИ
    # ============================================================

    @property
    def current_rank(self) -> int:
        return self.proc.get_rank() if self.proc else 0

    @property
    def current_states(self) -> int:
        return self.proc.get_n_states() if self.proc else 0

    @property
    def current_transitions(self) -> int:
        return self.proc.get_n_transitions() if self.proc else 0

    @property
    def current_words(self) -> int:
        return self.proc.get_n_words() if self.proc else 0

    @property
    def current_windows_closed(self) -> int:
        return self.proc.get_n_windows_closed() if self.proc else 0

    @property
    def total_processed(self) -> int:
        return self.global_t

    @property
    def window_fingerprints(self) -> List[WindowFingerprint]:
        return list(self._all_window_fingerprints)

    def metrics(self) -> Dict[str, int]:
        return {
            'total_processed': self.global_t,
            'rank': self.current_rank,
            'n_states': self.current_states,
            'n_transitions': self.current_transitions,
            'n_words': self.current_words,
            'n_windows_closed': self.current_windows_closed,
            'degree': self.degree,
            'path_length': self.path_length,
            'window_size': self.window_size,
            'overlap': self.overlap,
        }