# -*- coding: utf-8 -*-
"""
magnus/streaming/config_streaming.py
======================================
Конфигурация: ЧТО обрабатывать.
"""

import os

# ================================================================
# ПУТЬ К ДАННЫМ
# ================================================================

# Можно переопределить через переменную окружения
BASE = os.environ.get(
    'KADVI_DATA_DIR',
    "/home/m/Документы/лобачевский/турбо/KADVI/КАДВИ/КАДВИ/007"
)


# ================================================================
# НАБОРЫ ДАТЧИКОВ
# ================================================================

SENSOR_SETS = {
    'core': [
        'N tk', 'Qk/g',
        't gaz na vih iz GTD', 't masla na vihode iz GTD',
    ],
    
    'default': [
        'N tk', 'Qk/g', 'V red', 'V gen',
        't gaz na vih iz GTD', 't masla na vihode iz GTD', 'Pm v/vh',
    ],
    
    'extended': [
        'N tk', 'Qk/g', 'Pm v/vh', 'Pgaza na vihod',
        'P gaza na vhode d dozator', 'V red', 'V gen', 'V sau',
        't gaz na vih iz GTD', 't masla na vihode iz GTD',
        't vozd na vh v GTD', 'Ugol HD',
    ],
    
    'vibration': [
        'V red', 'V gen', 'V tk', 'V startera', 'V obg mufti', 'V sau',
    ],
    
    'temperature': [
        't gaz na vih iz GTD', 't masla na vihode iz GTD',
        't vozd na vh v GTD', 't gaza na vihode iz doz',
    ],
    
    'fuel': [
        'Qk/g', 'Pgaza na vihod', 'P gaza na vhode d dozator',
    ],
    
    'electric': [
        'I(A)', 'I(B)', 'I(C)', 'U(A)', 'U(B)', 'U(C)',
        'P(A)', 'P(B)', 'P(C)', 'kVAr', 'kVA', 'cos ?',
    ],
    
    'minimal': ['N tk', 'Qk/g'],
}


# ================================================================
# АКТИВНЫЙ НАБОР
# ================================================================

ACTIVE_SENSOR_SET = os.environ.get('MAGNUS_SENSOR_SET', 'default')

if ACTIVE_SENSOR_SET not in SENSOR_SETS:
    raise ValueError(
        f"Набор '{ACTIVE_SENSOR_SET}' не найден. "
        f"Доступные: {list(SENSOR_SETS.keys())}"
    )

SENSORS = SENSOR_SETS[ACTIVE_SENSOR_SET]


# ================================================================
# ПАРАМЕТРЫ ПРОЦЕССОРА
# ================================================================

PROCESSOR_PARAMS = {
    'alpha': 0.05,
    'n_sigma': 1.5,
    'min_count': 2,
    'degree': 3,
}


# ================================================================
# СОБЫТИЯ
# ================================================================

KNOWN_EVENTS = {
    '20260303': 'Остановка',
    '20260312': 'Остановка',
    '20260402': 'Остановка',
    '20260407': 'Остановка 11ч',
    '20260408': 'Остановка 13.7ч',
    '20260422': 'АНОМАЛИЯ',
    '20260423': 'Остановка',
}

KEY_DAYS = [
    '20260313', '20260303', '20260407',
    '20260408', '20260422', '20260423',
]


# ================================================================
# ВЫХОДНЫЕ ДАННЫЕ
# ================================================================

OUTPUT_DIR = os.environ.get(
    'MAGNUS_OUTPUT_DIR',
    "/home/m/Q/magnus/streaming_output"
)
os.makedirs(OUTPUT_DIR, exist_ok=True)
