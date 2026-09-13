# Changelog

Все значимые изменения в проекте Magnus.

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/)
Версионирование: [Semantic Versioning](https://semver.org/lang/ru/)

## [0.3.0] — 2026-09-13

### Added

**Streaming-ядро (Rust + Python)**
- `StreamingMagnus` — низкоуровневый потоковый процессор (Rust)
- `StreamingPipeline` — высокоуровневый pipeline
- Поддержка `degree=1..N`, `path_length`, `window_size`, `overlap`
- `process_batch_fast` — быстрая batch-обработка без аллокаций
- `soft_reset` в `state_graph` для режима с нахлёстом

**FAST-уровень (физические триггеры)**
- `fast_layer.rs` — детекция выбросов по z-score
- EMA среднего и дисперсии на каждый датчик
- Дебаунсинг и настраиваемые пороги

**Anomaly Predictor**
- `AnomalyPredictor` — двухуровневая система:
  - **FAST** — острые аварии (1-6 часов)
  - **SLOW** — медленная деградация (5-13 дней)
- YAML-конфигурация правил (`PredictorConfig`, `Rule`, `LevelConfig`)
- `load_predictor_config()` — загрузка из YAML
- `create_config_template()` — создание шаблона
- Классификация срочности (critical / high / medium / low)

**Visualizer**
- `generate_full_report()` — автоматический отчёт
- `plot_alerts_timeline()` — timeline алертов
- `plot_alerts_by_source()` — гистограмма по файлам
- `plot_sensors_degradation()` — динамика датчиков
- `plot_sensor_around_event()` — детальный график вокруг события

**CLI**
- `python -m magnus.streaming.run_predictor` — запуск Predictor
- `--config`, `--data`, `--output`, `--create-template`

**Загрузчики (`formats/`)**
- `NPYConcatenatedLoader` — memory-mapped загрузка NPY
- `AutoDetectLoader` — автоопределение CSV/TSV
- Поддержка Parquet, Excel

**Источники (`sources/`)**
- `StreamSource` — базовый класс
- `FileSource`, `OPCUASource`, `ModbusSource`, `MQTTSource`

**Утилиты и примеры**
- `tools/csv_to_npy_combined.py` — CSV → NPY (ускорение 40x)
- `benchmarks/streaming_benchmark.py`
- `examples/kadvi_007/` — пример для ГТЭА-007

### Changed
- `StreamingMagnus` — методы вместо property (`get_rank()`, `get_n_states()`)
- `process_batch` принимает плоский массив (не 2D)
- Структура `magnus/streaming/` реорганизована

### Fixed
- CI: добавлены `pandas`, `pyyaml` в зависимости
- Тесты `test_streaming.py` обновлены под актуальный API
- Python 3.12 совместимость

### Results

**На данных КАДВИ-007 (5,687,232 точек):**
- **17 алертов** всего
- **FAST**: 12 алертов (1-6 часов)
- **SLOW**: 5 алертов (5-13 дней)
- Все **7 известных событий** детектированы
- **Цепочка деградации 07.04 → 22.04** видна за 13 дней

**Производительность:**
- Streaming degree=2: 20s на 5.7M точек (285,000 точек/сек)
- Загрузка NPY: 0.3 ms (40,000x быстрее CSV)
- Тесты: 41 passed in 6.90s

### Testing
- 41 тест: core, groups, dictionary, spectral, streaming
- CI: GitHub Actions (Python 3.12 + Rust)

---

## [0.2.0] — Предыдущая версия
- Обновление README
- Исправления в тестах

## [0.1.0] — Первый релиз
- Базовая библиотека: `MagnusAlgebra`, `FRCodeRegistry`, `HomologySolver`
- Тесты: 26 тестов
