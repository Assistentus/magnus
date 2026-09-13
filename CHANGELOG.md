# Changelog

Все значимые изменения в проекте Magnus.

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/)
Версионирование: [Semantic Versioning](https://semver.org/lang/ru/)

## [0.3.0] — 2026-09-13

### Added

**Streaming-ядро (Rust + Python)**
- `StreamingMagnus` — низкоуровневый потоковый процессор
- `StreamingPipeline` — высокоуровневый pipeline
- Поддержка любого degree (1..N), path_length, window_size, overlap
- `process_batch_fast` — быстрая batch-обработка без аллокаций
- `soft_reset` в `state_graph` для режима с нахлёстом

**FAST-уровень (физические триггеры)**
- `fast_layer.rs` — детекция выбросов по z-score
- EMA среднего и дисперсии на каждый датчик
- Дебаунсинг и настраиваемые пороги

**Anomaly Predictor**
- `AnomalyPredictor` — двухуровневая система детекции:
  - **FAST** — острые отклонения (масштаб часов)
  - **SLOW** — медленная деградация (масштаб дней-недель)
- YAML-конфигурация правил (`PredictorConfig`, `Rule`, `LevelConfig`)
- `load_predictor_config()` — загрузка из YAML
- `create_config_template()` — создание шаблона
- Классификация срочности (critical / high / medium / low)

**Visualizer**
- `generate_full_report()` — автоматический отчёт
- `plot_alerts_timeline()` — timeline алертов
- `plot_alerts_by_source()` — распределение по источникам
- `plot_sensors_degradation()` — динамика датчиков
- `plot_sensor_around_event()` — детальный график вокруг события

**CLI**
- `python -m magnus.streaming.run_predictor` — запуск Predictor
- Опции: `--config`, `--data`, `--output`, `--create-template`

**Загрузчики (`formats/`)**
- `NPYConcatenatedLoader` — memory-mapped загрузка NPY
- `AutoDetectLoader` — автоопределение CSV/TSV
- Поддержка Parquet, Excel

**Источники (`sources/`)**
- `StreamSource` — базовый интерфейс источника
- `FileSource`, `OPCUASource`, `ModbusSource`, `MQTTSource`

**Утилиты и примеры**
- `tools/csv_to_npy_combined.py` — CSV → NPY
- `benchmarks/streaming_benchmark.py`
- `examples/` — примеры конфигураций

### Changed
- `StreamingMagnus` — методы вместо property (`get_rank()`, `get_n_states()`)
- `process_batch` принимает плоский массив (не 2D)
- Структура `magnus/streaming/` реорганизована
- API Predictor поддерживает YAML-конфигурацию

### Fixed
- CI: добавлены `pandas`, `pyyaml` в зависимости
- `test_streaming.py` обновлён под актуальный API
- Python 3.12 совместимость

### Testing
- 41 тест: core, groups, dictionary, spectral, streaming
- CI: GitHub Actions (Python 3.12 + Rust)

### Performance
- Streaming degree=2: ~285,000 точек/сек
- Загрузка NPY (memory-mapped): миллисекунды вместо секунд

---

## [0.2.0] — 2026-09-11
- Обновление README с научным описанием
- Исправления в тестах

## [0.1.0] — Первый релиз
- Базовая библиотека: `MagnusAlgebra`, `FRCodeRegistry`, `HomologySolver`, `TextPresentation`
- Тесты: 26 тестов
- Интеграция с Rust через PyO3
