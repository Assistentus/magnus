# -*- coding: utf-8 -*-
"""
magnus/streaming/sources/opcua_source.py
==========================================
Источник: OPC UA.

Стандарт для современных SCADA и ГТУ.
"""

from typing import Iterator, Dict, Any, List, Optional
import time
import numpy as np

from .base import StreamSource


class OPCUASource(StreamSource):
    """
    Источник OPC UA.
    
    Требует: pip install asyncua
    
    Пример:
        source = OPCUASource(
            url='opc.tcp://192.168.1.10:4840',
            node_ids=[
                'ns=2;s=Sensors.N_tk',
                'ns=2;s=Sensors.Qk_g',
                'ns=2;s=Sensors.V_red',
            ],
            sensors=['N tk', 'Qk/g', 'V red'],
            interval_ms=1000,
        )
        for item in source:
            process(item['values'])
    """
    
    def __init__(self,
                 url: str,
                 node_ids: List[str],
                 sensors: List[str],
                 interval_ms: int = 1000,
                 source_name: str = 'opcua'):
        """
        Args:
            url: адрес OPC UA сервера
            node_ids: список NodeId для чтения
            sensors: имена датчиков (для отображения)
            interval_ms: интервал опроса в мс
            source_name: имя источника
        """
        super().__init__(sensors)
        
        if len(node_ids) != len(sensors):
            raise ValueError(
                f"node_ids ({len(node_ids)}) != sensors ({len(sensors)})"
            )
        
        self.url = url
        self.node_ids = node_ids
        self.interval_ms = interval_ms
        self.source_name = source_name
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        try:
            import asyncio
            from asyncua import Client
        except ImportError:
            raise ImportError(
                "Требуется asyncua. Установите: pip install asyncua"
            )
        
        async def read_loop():
            async with Client(url=self.url) as client:
                nodes = [client.get_node(nid) for nid in self.node_ids]
                
                while True:
                    values = []
                    for node in nodes:
                        try:
                            val = await node.read_value()
                            values.append(float(val))
                        except Exception as e:
                            values.append(0.0)
                    
                    yield {
                        'source': self.source_name,
                        'values': np.array(values, dtype=np.float64),
                        'timestamp': time.time(),
                    }
                    
                    await asyncio.sleep(self.interval_ms / 1000.0)
        
        # Запускаем async в синхронном генераторе
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        gen = read_loop()
        try:
            while True:
                yield loop.run_until_complete(gen.__anext__())
        except StopAsyncIteration:
            return
        finally:
            loop.close()