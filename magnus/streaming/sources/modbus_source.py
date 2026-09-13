# -*- coding: utf-8 -*-
"""
magnus/streaming/sources/modbus_source.py
===========================================
Источник: Modbus TCP/RTU.

Классика для промышленных контроллеров.
"""

from typing import Iterator, Dict, Any, List, Optional
import time
import numpy as np

from .base import StreamSource


class ModbusSource(StreamSource):
    """
    Источник Modbus TCP.
    
    Требует: pip install pymodbus
    
    Пример:
        source = ModbusSource(
            host='192.168.1.10',
            port=502,
            unit_id=1,
            registers=[100, 101, 102, 103, 104],
            sensors=['N tk', 'Qk/g', 'V red', 'V gen', 'Pm'],
            scale=[0.1, 0.01, 0.001, 0.001, 0.01],
            interval_ms=1000,
        )
        for item in source:
            process(item['values'])
    """
    
    def __init__(self,
                 host: str,
                 registers: List[int],
                 sensors: List[str],
                 port: int = 502,
                 unit_id: int = 1,
                 scale: Optional[List[float]] = None,
                 interval_ms: int = 1000,
                 source_name: str = 'modbus'):
        """
        Args:
            host: IP-адрес Modbus сервера
            registers: список адресов регистров
            sensors: имена датчиков
            port: порт (502 по умолчанию)
            unit_id: ID устройства
            scale: коэффициенты масштабирования
            interval_ms: интервал опроса
            source_name: имя источника
        """
        super().__init__(sensors)
        
        if len(registers) != len(sensors):
            raise ValueError("registers и sensors разной длины")
        
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.registers = registers
        self.scale = scale or [1.0] * len(registers)
        self.interval_ms = interval_ms
        self.source_name = source_name
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        try:
            from pymodbus.client import ModbusTcpClient
        except ImportError:
            raise ImportError(
                "Требуется pymodbus. Установите: pip install pymodbus"
            )
        
        client = ModbusTcpClient(host=self.host, port=self.port)
        client.connect()
        
        try:
            while True:
                values = []
                
                for reg in self.registers:
                    try:
                        result = client.read_holding_registers(
                            reg, count=1, slave=self.unit_id
                        )
                        if result.isError():
                            values.append(0.0)
                        else:
                            values.append(float(result.registers[0]))
                    except Exception:
                        values.append(0.0)
                
                # Масштабирование
                scaled = np.array([
                    v * s for v, s in zip(values, self.scale)
                ], dtype=np.float64)
                
                yield {
                    'source': self.source_name,
                    'values': scaled,
                    'timestamp': time.time(),
                }
                
                time.sleep(self.interval_ms / 1000.0)
        finally:
            client.close()