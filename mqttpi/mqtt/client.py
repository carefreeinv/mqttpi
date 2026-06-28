"""Shared MQTT connection for mqttpi subsystems."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Optional

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)


class MqttConnection:
    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: str = "",
        password: str = "",
        client_id: str = "mqttpi",
        retain: bool = True,
        qos: int = 1,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.retain = retain
        self.qos = qos
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
        )
        if username:
            self._client.username_pw_set(username, password or None)
        self._message_handler: Optional[Callable[[str, str], None]] = None
        self._client.on_message = self._on_message

    def set_message_handler(
        self, handler: Optional[Callable[[str, str], None]]
    ) -> None:
        self._message_handler = handler

    def connect(self) -> None:
        self._client.connect(self.host, self.port, keepalive=60)
        self._client.loop_start()
        log.info("MQTT connected to %s:%s", self.host, self.port)

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def subscribe(self, topic: str) -> None:
        self._client.subscribe(topic, qos=self.qos)

    def publish(self, topic: str, payload: str) -> None:
        self._client.publish(topic, payload, retain=self.retain, qos=self.qos)

    def publish_json(self, topic: str, payload: Dict[str, Any]) -> None:
        self.publish(topic, json.dumps(payload))

    def publish_availability(self, base_topic: str, online: bool) -> None:
        payload = "online" if online else "offline"
        self.publish(f"{base_topic.rstrip('/')}/status", payload)

    def _on_message(
        self,
        _client: mqtt.Client,
        _userdata: object,
        msg: mqtt.MQTTMessage,
    ) -> None:
        if self._message_handler is None:
            return
        try:
            payload = msg.payload.decode("utf-8")
        except UnicodeDecodeError:
            log.warning("Ignoring non-UTF-8 MQTT payload on %s", msg.topic)
            return
        self._message_handler(msg.topic, payload)