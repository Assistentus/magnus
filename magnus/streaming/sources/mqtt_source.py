# -*- coding: utf-8 -*-
"""
magnus/streaming/sources/mqtt_source.py
==========================================
Источник: MQTT.

Для IoT-датчиков и SCADA с MQTT-экспортом.
"""

from typing import Iterator, Dict, Any, List, Optional
import time
import json
import numpy as np
from queue import Queue, Empty
import threading

from .base import StreamSource


class MQTTSource(StreamSource):
    """
    Источник MQTT.
    
    Требует: pip install paho-mqtt
    
    Пример:
        source = MQTTSource(
            broker='192.168.1.10',
            topic='gtu/sensors',
            sensors=['N tk', 'Qk/g', 'V red'],
        )
        for item in source:
            process(item['values'])
    """
    
    def __init__(self,
                 broker: str,
                 sensors: List[str],
                 topic: str = 'gtu/+/sensors',
                 port: int = 1883,
                 source_name: str = 'mqtt',
                 json_fields: Optional[List[str]] = None):
        """
        Args:
            broker: адрес MQTT брокера
            sensors: имена датчиков
            topic: MQTT topic
            port: порт (1883)
            source_name: имя источника
            json_fields: имена полей в JSON (если данные в JSON)
        """
        super().__init__(sensors)
        
        self.broker = broker
        self.port = port
        self.topic = topic
        self.source_name = source_name
        self.json_fields = json_fields or sensors
        
        self._queue = Queue()
        self._client = None
    
    def _on_message(self, client, userdata, msg):
        """Callback на новое сообщение."""
        try:
            payload = msg.payload.decode('utf-8')
            
            # Пробуем JSON
            try:
                data = json.loads(payload)
                values = [float(data.get(f, 0.0)) 
                          for f in self.json_fields]
            except json.JSONDecodeError:
                # CSV
                values = [float(x.strip()) 
                          for x in payload.split(',')]
            
            self._queue.put({
                'source': msg.topic,
                'values': np.array(values, dtype=np.float64),
                'timestamp': time.time(),
            })
        except Exception as e:
            print(f"MQTT parse error: {e}")
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            raise ImportError(
                "Требуется paho-mqtt. Установите: pip install paho-mqtt"
            )
        
        self._client = mqtt.Client()
        self._client.on_message = self._on_message
        self._client.connect(self.broker, self.port, 60)
        self._client.subscribe(self.topic)
        
        # Запускаем MQTT в отдельном потоке
        self._client.loop_start()
        
        try:
            while True:
                try:
                    item = self._queue.get(timeout=1.0)
                    yield item
                except Empty:
                    continue
        finally:
            self._client.loop_stop()
            self._client.disconnect()