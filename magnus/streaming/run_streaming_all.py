# -*- coding: utf-8 -*-
"""
magnus/streaming/run_streaming_all.py
=======================================
Обработка всех файлов через StreamingPipeline.
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from magnus.streaming.streaming_pipeline import StreamingPipeline
from magnus.streaming.config_streaming import (
    BASE, SENSOR_SETS, KNOWN_EVENTS,
    PROCESSOR_PARAMS, OUTPUT_DIR
)


def main():
    parser = argparse.ArgumentParser(
        description='Потоковая обработка данных КАДВИ'
    )
    parser.add_argument(
        '--sensors', '-s',
        default=None,                      # ← НЕ required=True
        choices=list(SENSOR_SETS.keys()),
        help='Набор датчиков (обязательно, если не указан --list)'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='Показать все наборы датчиков'
    )
    args = parser.parse_args()
    
    # ============================================================
    # ПОКАЗАТЬ НАБОРЫ (без обработки)
    # ============================================================
    if args.list:
        print("Доступные наборы датчиков:\n")
        for name, sensors in SENSOR_SETS.items():
            print(f"  {name:<15} ({len(sensors)} датчиков)")
            for s in sensors:
                print(f"    - {s}")
            print()
        return
    
    # ============================================================
    # ПРОВЕРКА: если не --list, то --sensors обязателен
    # ============================================================
    if args.sensors is None:
        parser.error(
            "Параметр --sensors/-s обязателен "
            "(или используйте --list для показа наборов)"
        )
    
    sensors = SENSOR_SETS[args.sensors]
    
    print(f"📂 Набор датчиков: {args.sensors} ({len(sensors)} шт.)")
    for s in sensors:
        print(f"   - {s}")
    print()
    
    files = sorted([f for f in os.listdir(BASE) if f.endswith('.csv')])
    filepaths = [os.path.join(BASE, f) for f in files]
    dates = [f.replace('.csv', '') for f in files]
    
    print(f"📂 Обработка {len(files)} файлов")
    
    pipeline = StreamingPipeline(sensors=sensors, **PROCESSOR_PARAMS)
    result = pipeline.process_files(filepaths, dates, verbose=True)
    
    df = result.to_dataframe()
    df['event'] = df['date'].map(KNOWN_EVENTS).fillna('')
    
    output_file = os.path.join(OUTPUT_DIR, f'streaming_all_{args.sensors}.csv')
    df.to_csv(output_file, index=False)
    
    print(f"\n{'='*80}")
    print(f"ИТОГИ:")
    print(f"  Набор:            {args.sensors}")
    print(f"  Датчиков:         {len(result.sensors_used)}")
    print(f"  Точек:            {result.total_points:,}")
    print(f"  Финальный ранг:   {result.total_rank:,}")
    print(f"\n📁 Сохранено: {output_file}")


if __name__ == "__main__":
    main()
