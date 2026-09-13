# -*- coding: utf-8 -*-
"""
magnus/streaming/formats/base.py
==================================
Базовый класс для загрузчиков данных.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np


class BaseLoader(ABC):
    """
    Базовый класс загрузчика.
    
    Все загрузчики должны возвращать C-contiguous массив 
    формы (n_points, n_sensors) или None при ошибке.
    """
    
    @abstractmethod
    def __call__(self, filepath: str, 
                  sensors: List[str]) -> Optional[np.ndarray]:
        """
        Загружает данные из файла.
        
        Args:
            filepath: путь к файлу
            sensors: список датчиков
            
        Returns:
            np.ndarray формы (n_points, n_sensors) или None
        """
        pass