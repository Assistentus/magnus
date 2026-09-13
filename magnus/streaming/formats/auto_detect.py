# -*- coding: utf-8 -*-
"""
magnus/streaming/formats/auto_detect.py
=========================================
АВТООПРЕДЕЛЕНИЕ формата файла.

Автоматически определяет:
- Разделитель колонок (',', ';', '\\t', '|', ' ')
- Десятичный разделитель (',' или '.')
- Кодировку (UTF-8, CP1251, Latin-1)
- Перенос строк

Работает без явных параметров.
"""

import os
import csv
import codecs
import numpy as np
import pandas as pd
from typing import List, Optional, Tuple, Dict
from .base import BaseLoader


# ================================================================
# АВТООПРЕДЕЛЕНИЕ КОДИРОВКИ
# ================================================================

def detect_encoding(filepath: str, n_bytes: int = 100_000) -> str:
    """
    Определяет кодировку файла.
    
    Пробует: utf-8, utf-8-sig, cp1251, latin-1.
    """
    candidates = ['utf-8', 'utf-8-sig', 'cp1251', 'latin-1']
    
    with open(filepath, 'rb') as f:
        raw = f.read(n_bytes)
    
    for enc in candidates:
        try:
            raw.decode(enc)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    
    return 'latin-1'  # fallback


# ================================================================
# АВТООПРЕДЕЛЕНИЕ РАЗДЕЛИТЕЛЯ
# ================================================================

def detect_delimiter(filepath: str, encoding: str, 
                      sample_lines: int = 10) -> str:
    """
    Определяет разделитель колонок.
    
    Читает первые N строк и смотрит, какой разделитель
    даёт наиболее стабильное число колонок.
    """
    candidates = [';', ',', '\t', '|', ' ']
    
    # Читаем первые N строк
    lines = []
    try:
        with open(filepath, 'r', encoding=encoding, errors='replace') as f:
            for i, line in enumerate(f):
                if i >= sample_lines:
                    break
                line = line.strip()
                if line:
                    lines.append(line)
    except Exception:
        return ','
    
    if not lines:
        return ','
    
    best_sep = ','
    best_score = -1
    
    for sep in candidates:
        # Считаем число колонок в каждой строке
        counts = [line.count(sep) for line in lines]
        
        if not counts or max(counts) == 0:
            continue
        
        # Стабильность: std должен быть мал
        mean_count = np.mean(counts)
        std_count = np.std(counts)
        
        # Скоринг: много колонок + низкий std
        score = mean_count - std_count * 5
        
        if score > best_score:
            best_score = score
            best_sep = sep
    
    return best_sep


# ================================================================
# АВТООПРЕДЕЛЕНИЕ ДЕСЯТИЧНОГО РАЗДЕЛИТЕЛЯ
# ================================================================

def detect_decimal(filepath: str, encoding: str, 
                    delimiter: str, sample_lines: int = 20) -> str:
    """
    Определяет десятичный разделитель (',' или '.').
    
    Идея: смотрим на числа в первом столбце данных.
    Если есть "1,5" — decimal = ','
    Если есть "1.5" — decimal = '.'
    """
    try:
        with open(filepath, 'r', encoding=encoding, errors='replace') as f:
            # Пропускаем заголовок
            f.readline()
            
            comma_score = 0
            dot_score = 0
            
            for i, line in enumerate(f):
                if i >= sample_lines:
                    break
                
                parts = line.strip().split(delimiter)
                for part in parts[:5]:  # первые 5 колонок
                    part = part.strip()
                    # Ищем "1,5" или "1.5"
                    if ',' in part and part.replace(',', '').replace('-', '').replace('+', '').isdigit():
                        comma_score += 1
                    if '.' in part and part.replace('.', '').replace('-', '').replace('+', '').isdigit():
                        dot_score += 1
            
            return ',' if comma_score >= dot_score else '.'
    except Exception:
        return '.'


# ================================================================
# АВТООПРЕДЕЛЕНИЕ ПЕРЕНОСА СТРОК
# ================================================================

def detect_line_ending(filepath: str, n_bytes: int = 10000) -> str:
    """Определяет перенос строк: '\\n' или '\\r\\n'."""
    try:
        with open(filepath, 'rb') as f:
            raw = f.read(n_bytes)
        
        if b'\r\n' in raw:
            return '\r\n'
        elif b'\r' in raw:
            return '\r'
        else:
            return '\n'
    except Exception:
        return '\n'


# ================================================================
# АВТО-ЗАГРУЗЧИК
# ================================================================

class AutoDetectLoader(BaseLoader):
    """
    Загрузчик с АВТООПРЕДЕЛЕНИЕМ формата.
    
    Сам определяет:
    - Кодировку
    - Разделитель колонок
    - Десятичный разделитель
    - Перенос строк
    
    Пример:
        loader = AutoDetectLoader()
        data = loader('file.csv', ['N tk', 'Qk/g'])
    """
    
    def __init__(self,
                 normalize_columns: bool = True,
                 skip_missing: bool = True,
                 verbose: bool = False):
        """
        Args:
            normalize_columns: убирать пробелы/табы из имён
            skip_missing: пропускать отсутствующие датчики
            verbose: печатать определённые параметры
        """
        self.normalize_columns = normalize_columns
        self.skip_missing = skip_missing
        self.verbose = verbose
        
        # Кэш определённых параметров (по пути)
        self._cache: Dict[str, Dict] = {}
    
    def _detect_format(self, filepath: str) -> Dict:
        """Определяет параметры формата (с кэшированием)."""
        if filepath in self._cache:
            return self._cache[filepath]
        
        encoding = detect_encoding(filepath)
        delimiter = detect_delimiter(filepath, encoding)
        decimal = detect_decimal(filepath, encoding, delimiter)
        line_ending = detect_line_ending(filepath)
        
        params = {
            'encoding': encoding,
            'delimiter': delimiter,
            'decimal': decimal,
            'line_ending': line_ending,
        }
        
        if self.verbose:
            print(f"  🔍 {os.path.basename(filepath)}: "
                  f"enc={encoding}, sep={repr(delimiter)}, "
                  f"dec={repr(decimal)}, eol={repr(line_ending)}")
        
        self._cache[filepath] = params
        return params
    
    def _read_csv(self, filepath: str, params: Dict) -> Optional[pd.DataFrame]:
        """Читает файл через pandas с определёнными параметрами."""
        try:
            # Для длинных файлов — читаем только первые строки для определения
            # потом читаем полностью
            df = pd.read_csv(
                filepath,
                sep=params['delimiter'],
                decimal=params['decimal'],
                encoding=params['encoding'],
                engine='python',
            )
            return df
        except Exception as e:
            # Fallback: пробуем C-engine
            try:
                df = pd.read_csv(
                    filepath,
                    sep=params['delimiter'],
                    decimal=params['decimal'],
                    encoding=params['encoding'],
                )
                return df
            except Exception as e2:
                print(f"  ⚠️ AutoDetect: не удалось прочитать "
                      f"{os.path.basename(filepath)}: {e2}")
                return None
    
    @staticmethod
    def _normalize_columns_inplace(df: pd.DataFrame) -> None:
        """Нормализует имена колонок."""
        df.columns = [str(c).strip().replace('\t', ' ')
                      for c in df.columns]
    
    def __call__(self, filepath: str,
                  sensors: List[str]) -> Optional[np.ndarray]:
        """
        Загружает данные с автоопределением формата.
        """
        # 1. Определяем формат
        params = self._detect_format(filepath)
        
        # 2. Читаем
        df = self._read_csv(filepath, params)
        if df is None:
            return None
        
        # 3. Нормализуем колонки
        if self.normalize_columns:
            self._normalize_columns_inplace(df)
        
        # 4. Определяем доступные датчики
        if self.skip_missing:
            available = [s for s in sensors if s in df.columns]
        else:
            missing = [s for s in sensors if s not in df.columns]
            if missing:
                print(f"  ⚠️ Отсутствуют: {missing}")
                return None
            available = sensors
        
        if not available:
            return None
        
        # 5. Извлекаем данные
        try:
            sub = df[available]
            
            # Конвертируем в float
            for col in sub.columns:
                sub[col] = pd.to_numeric(sub[col], errors='coerce')
            
            # Заполняем пропуски
            sub = sub.ffill().bfill()
            
            data = sub.values
            
            return np.ascontiguousarray(data, dtype=np.float64)
        except Exception as e:
            print(f"  ⚠️ Ошибка извлечения данных: {e}")
            return None
    
    def get_format_info(self, filepath: str) -> Dict:
        """Возвращает определённые параметры формата."""
        return self._detect_format(filepath)
    
    def clear_cache(self):
        """Очищает кэш."""
        self._cache.clear()