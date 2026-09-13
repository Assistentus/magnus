# -*- coding: utf-8 -*-
"""
Анализ роста памяти Magnus.
Показывает как растут состояния, переходы, ранг.
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, '/home/m/Q/magnus')

from magnus.streaming import StreamingPipeline
from magnus.streaming.config_streaming import BASE, SENSOR_SETS, PROCESSOR_PARAMS, OUTPUT_DIR


def main():
    # Используем extended (12 датчиков)
    sensors = SENSOR_SETS['extended']
    
    print(f"📊 Анализ роста памяти")
    print(f"   Датчиков: {len(sensors)}")
    
    # Файлы
    files = sorted([f for f in os.listdir(BASE) if f.endswith('.csv')])
    filepaths = [os.path.join(BASE, f) for f in files]
    dates = [f.replace('.csv', '') for f in files]
    
    # Pipeline
    pipeline = StreamingPipeline(sensors=sensors, **PROCESSOR_PARAMS)
    
    # Обработка
    result = pipeline.process_files(filepaths, dates, verbose=False)
    
    # Собираем данные
    rows = []
    cumulative_states = 0
    cumulative_transitions = 0
    
    for day in result.days:
        rows.append({
            'date': day.date,
            'rank': day.rank_end,
            'n_states': day.n_states_end,
            'n_transitions': day.n_transitions_end,
        })
    
    df = pd.DataFrame(rows)
    
    # Оценка памяти
    # StateGraph: ~44 байт на состояние + ~32 байт на переход
    # RankTracker: ~72 байт на пивот
    
    df['memory_states_MB'] = df['n_states'] * 44 / 1024 / 1024
    df['memory_transitions_MB'] = df['n_transitions'] * 32 / 1024 / 1024
    df['memory_rank_MB'] = df['rank'] * 72 / 1024 / 1024
    df['memory_total_MB'] = (df['memory_states_MB'] + 
                              df['memory_transitions_MB'] + 
                              df['memory_rank_MB'])
    
    # Вывод
    print(f"\n{'Дата':<12} {'Ранг':>10} {'Состояний':>12} "
          f"{'Переходов':>12} {'Память (МБ)':>12}")
    print("-"*70)
    
    for _, row in df.iterrows():
        print(f"{row['date']:<12} {row['rank']:>10,} "
              f"{row['n_states']:>12,} {row['n_transitions']:>12,} "
              f"{row['memory_total_MB']:>11.2f}")
    
    # Прогноз
    print(f"\n{'='*70}")
    print(f"ПРОГНОЗ РОСТА ПАМЯТИ:")
    print(f"{'='*70}")
    
    days = len(df)
    last_row = df.iloc[-1]
    
    # Скорость роста
    memory_per_day = last_row['memory_total_MB'] / days
    rank_per_day = last_row['rank'] / days
    states_per_day = last_row['n_states'] / days
    
    print(f"\nСкорость роста:")
    print(f"  Ранг:        {rank_per_day:>10,.0f} в день")
    print(f"  Состояний:   {states_per_day:>10,.0f} в день")
    print(f"  Память:      {memory_per_day:>10,.3f} МБ в день")
    
    print(f"\nПрогноз:")
    for period, days_est in [
        ('1 месяц', 30),
        ('6 месяцев', 180),
        ('1 год', 365),
        ('3 года', 1095),
        ('10 лет', 3650),
    ]:
        memory_est = memory_per_day * days_est
        rank_est = rank_per_day * days_est
        states_est = states_per_day * days_est
        
        if memory_est < 1024:
            mem_str = f"{memory_est:.1f} МБ"
        else:
            mem_str = f"{memory_est/1024:.2f} ГБ"
        
        print(f"  {period:<12}: rank={rank_est:>12,.0f}, "
              f"states={states_est:>10,.0f}, память={mem_str}")
    
    # Визуализация
    fig, axes = plt.subplots(2, 2, figsize=(18, 10))
    
    x = range(len(df))
    
    # Ранг
    ax = axes[0, 0]
    ax.plot(x, df['rank'], 'r-', linewidth=2)
    ax.set_title('Накопительный ранг')
    ax.set_ylabel('Ранг')
    ax.grid(True, alpha=0.3)
    
    # Состояния
    ax = axes[0, 1]
    ax.plot(x, df['n_states'], 'b-', linewidth=2)
    ax.set_title('Накопительные состояния')
    ax.set_ylabel('Состояний')
    ax.grid(True, alpha=0.3)
    
    # Переходы
    ax = axes[1, 0]
    ax.plot(x, df['n_transitions'], 'g-', linewidth=2)
    ax.set_title('Накопительные переходы')
    ax.set_ylabel('Переходов')
    ax.grid(True, alpha=0.3)
    
    # Память
    ax = axes[1, 1]
    ax.plot(x, df['memory_total_MB'], 'purple', linewidth=2)
    ax.set_title('Память Magnus (МБ)')
    ax.set_ylabel('МБ')
    ax.grid(True, alpha=0.3)
    
    # Прогноз на графике
    ax.axhline(memory_per_day * 365, color='red', linestyle='--', 
              alpha=0.5, label=f'1 год: {memory_per_day * 365:.1f} МБ')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'memory_growth.png'), dpi=150)
    print(f"\n📊 Сохранено: {OUTPUT_DIR}/memory_growth.png")
    
    # CSV
    df.to_csv(os.path.join(OUTPUT_DIR, 'memory_growth.csv'), index=False)
    
    return df


if __name__ == "__main__":
    main()