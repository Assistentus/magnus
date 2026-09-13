# -*- coding: utf-8 -*-
"""
magnus/streaming/sources/base.py
==================================
Базовый класс источника потока.

Любой источник (OPC UA, Modbus, MQTT, файл) реализует этот интерфейс.
"""

from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, List, Optional
import numpy as np


class StreamSource(ABC):
    """
    Базовый источник потока данных.
    
    Yields словари вида:
        {'source': 'источник', 'values': np.array([...])}
    
    Пример:
        source = MySource(sensors=['s1', 's2'])
        for item in source:
            print(item['values'])
    """
    
    def __init__(self, sensors: List[str]):
        """
        Args:
            sensors: список имён датчиков, которые нужно читать
        """
        if not sensors:
            raise ValueError("sensors не может быть пустым")
        self.sensors = list(sensors)
    
    @abstractmethod
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """
        Итератор по точкам.
        
        Yields:
            {'source': str, 'values': np.ndarray, 'timestamp': optional}
        """
        pass
    
    def close(self):
        """Закрыть соединение (если нужно)."""
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()