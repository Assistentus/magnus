# Magnus Streaming Module

Потоковая обработка данных с датчиков на основе f r-codes.

## Ключевые принципы

1. **Каждая точка обрабатывается ОДИН РАЗ** — нет batch-пересчётов
2. **НЕТ СКОЛЬЗЯЩЕГО ОКНА** — вся история накапливается
3. **Ранг монотонно растёт** — никогда не убывает
4. **Память = O(уникальные состояния)** — не зависит от числа точек

## Быстрый старт (Python)

```python
from magnus.streaming import StreamingMagnus
import numpy as np

proc = StreamingMagnus(n_sensors=7)

for x in data:  # x.shape = (7,)
    result = proc.process(x)
    if result['rank_increased']:
        print(f"t={result['t']}, rank={result['rank']}")