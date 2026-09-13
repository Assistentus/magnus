# -*- coding: utf-8 -*-
"""
magnus/streaming/sources/file_source.py
=========================================
Источник: файлы на диске.

Для тестов и batch-обработки.
"""

from typing import Iterator, Dict, Any, List, Optional
import os
import numpy as np
from glob import glob

from .base import StreamSource
from ..formats import AutoDetectLoader


class FileSource(StreamSource):
    """
    Источник: файлы.
    
    Читает файлы по порядку, эмитит точки.
    
    Пример:
        source = FileSource(
            path='/data/gtu',
            pattern='*.csv',
            sensors=['N tk', 'Qk/g'],
        )
        for item in source:
            print(item['source'], item['values'])
    """
    
    def __init__(self,
                 path: str,
                 sensors: List[str],
                 pattern: str = '*.csv',
                 loader = None):
        super().__init__(sensors)
        
        self.path = path
        self.pattern = pattern
        self.loader = loader or AutoDetectLoader()
        
        # Находим все файлы
        if os.path.isdir(path):
            self.files = sorted(glob(os.path.join(path, pattern)))
        elif os.path.isfile(path):
            self.files = [path]
        else:
            self.files = []
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        for filepath in self.files:
            data = self.loader(filepath, self.sensors)
            
            if data is None:
                continue
            
            source_name = os.path.basename(filepath).rsplit('.', 1)[0]
            
            for row in data:
                yield {
                    'source': source_name,
                    'values': np.ascontiguousarray(row, dtype=np.float64),
                }