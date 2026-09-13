# -*- coding: utf-8 -*-
"""
magnus/streaming/run_predictor.py
==================================
Готовый скрипт: запускает Predictor из YAML-конфига.

Использование:
    # Со своим конфигом:
    python -m magnus.streaming.run_predictor --config my_config.yaml --data data/npy

    # С параметрами по умолчанию:
    python -m magnus.streaming.run_predictor
"""

import argparse
from pathlib import Path

from . import (
    NPYConcatenatedLoader,
    AnomalyPredictor,
    generate_full_report,
)
from .predictor import create_config_template


# ================================================================
# НАСТРОЙКИ ПО УМОЛЧАНИЮ
# ================================================================

DEFAULT_DATA_DIR = 'data/kadvi_007_npy'
DEFAULT_CONFIG = 'examples/kadvi_007/predictor_config.yaml'
DEFAULT_OUTPUT = 'magnus_output/kadvi_007'

# Известные события (для отметки на графиках)
KNOWN_EVENTS = {
    '20260303': 'Остановка',
    '20260312': 'Остановка',
    '20260402': 'Остановка',
    '20260407': 'Остановка 11ч',
    '20260408': 'Остановка 13.7ч',
    '20260422': 'АНОМАЛИЯ',
    '20260423': 'Остановка',
}

SENSORS_TO_PLOT = [
    'V red',
    'V gen',
    'Pgaza na vihod',
    't gaz na vih iz GTD',
    'N tk',
    't vozd na vh v GTD',
]


# ================================================================
# ЗАПУСК
# ================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Magnus Predictor — предсказание аномалий'
    )
    parser.add_argument('--data', '-d',
                        default=DEFAULT_DATA_DIR,
                        help=f'Директория с NPY (по умолчанию: {DEFAULT_DATA_DIR})')
    parser.add_argument('--config', '-c',
                        default=DEFAULT_CONFIG,
                        help=f'YAML-конфиг (по умолчанию: {DEFAULT_CONFIG})')
    parser.add_argument('--output', '-o',
                        default=DEFAULT_OUTPUT,
                        help=f'Директория для отчёта (по умолчанию: {DEFAULT_OUTPUT})')
    parser.add_argument('--create-template',
                        metavar='PATH',
                        help='Создать шаблон конфига и выйти')

    args = parser.parse_args()

    # Если запрошен шаблон
    if args.create_template:
        create_config_template(args.create_template)
        print()
        print('Отредактируйте шаблон и запустите:')
        print(f'  python -m magnus.streaming.run_predictor '
              f'--config {args.create_template} --data {args.data}')
        return

    print('=' * 80)
    print('MAGNUS PREDICTOR — предсказание аномалий')
    print('=' * 80)
    print()

    # Проверка конфига
    if not Path(args.config).exists():
        print(f'❌ Конфиг не найден: {args.config}')
        print()
        print(f'Создайте шаблон:')
        print(f'  python -m magnus.streaming.run_predictor '
              f'--create-template {args.config}')
        return

    # 1. Загрузка
    print(f'📂 Данные:    {args.data}')
    loader = NPYConcatenatedLoader(data_dir=args.data, use_mmap=True)
    print(f'   {loader}')
    print()

    print(f'📋 Конфиг:    {args.config}')

    # 2. Predictor из YAML
    predictor = AnomalyPredictor.from_config(
        config_path=args.config,
        sensors=loader.sensors,
    )
    print(f'   name:      {predictor.config.name}')
    print(f'   fast:      {len(predictor.config.fast.rules)} правил, '
          f'min_score={predictor.config.fast.min_score}')
    print(f'   slow:      {len(predictor.config.slow.rules)} правил, '
          f'min_score={predictor.config.slow.min_score}')
    print()

    # 3. Запуск
    print('🔍 Запуск Predictor...')
    result = predictor.predict(loader)

    # 4. Вывод
    print()
    print(result.summary())
    result.print_alerts()

    # 5. Отчёт
    print()
    generate_full_report(
        predictor_result=result,
        loader=loader,
        output_dir=args.output,
        known_events=KNOWN_EVENTS,
        sensors_to_plot=SENSORS_TO_PLOT,
    )

    print()
    print('=' * 80)
    print('ГОТОВО')
    print('=' * 80)
    print()
    print(f'Отчёт: {args.output}/')


if __name__ == '__main__':
    main()