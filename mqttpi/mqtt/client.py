"""Shared MQTT connection for mqttpi subsystems."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable, Dict, List, Optional

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)

PAYLOAD_AVAILABLE = "online"
PAYLOAD_NOT_AVAILABLE = "offline"

ConnectCallback = Callable[[], None]


def availability_topic_for(base_topic: str) -> str:
    """Return the availability topic (``{base_topic}/status``) for a base topic."""
    return f"{base_topic.rstrip('/')}/status"


class MqttConnection:
    """One paho client shared by every subsystem in a process.

    When an availability topic is known (``availability_topic`` or
    ``base_topic``), the connection registers a retained MQTT Last Will of
    ``payload_not_available`` on it before connecting, and publishes a retained
    ``payload_available`` after *every* successful (re)connect. If the process
    dies without a clean disconnect, the broker publishes the will so consumers
    see the node go offline. Pass ``will=False`` to opt out.
    """

    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: str = "",
        password: str = "",
        client_id: str = "mqttpi",
        retain: bool = True,
        qos: int = 1,
        base_topic: Optional[str] = None,
        availability_topic: Optional[str] = None,
        will: bool = True,
        payload_available: str = PAYLOAD_AVAILABLE,
        payload_not_available: str = PAYLOAD_NOT_AVAILABLE,
        keepalive: int = 60,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.retain = retain
        self.qos = qos
        self.keepalive = int(keepalive)
        if availability_topic is None and base_topic is not None:
            availability_topic = availability_topic_for(base_topic)
        self.availability_topic = availability_topic
        self.will_enabled = bool(will and availability_topic)
        self.payload_available = payload_available
        self.payload_not_available = payload_not_available

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
        )
        if username:
            self._client.username_pw_set(username, password or None)
        self._message_handler: Optional[Callable[[str, str], None]] = None
        self._connect_callbacks: List[ConnectCallback] = []
        self._connected = threading.Event()
        self._client.on_message = self._on_message
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    # -- configuration -------------------------------------------------

    def set_message_handler(
        self, handler: Optional[Callable[[str, str], None]]
    ) -> None:
        self._message_handler = handler

    def add_connect_callback(self, callback: ConnectCallback) -> None:
        """Run ``callback`` after every successful (re)connect.

        Callbacks run on the paho network thread, after the availability
        ``online`` message has been queued. Keep them short.
        """
        self._connect_callbacks.append(callback)

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    # -- lifecycle -----------------------------------------------------

    def connect(self) -> None:
        if self.will_enabled:
            assert self.availability_topic is not None
            self._client.will_set(
                self.availability_topic,
                self.payload_not_available,
                qos=self.qos,
                retain=True,
            )
        self._client.connect(self.host, self.port, keepalive=self.keepalive)
        self._client.loop_start()
        log.info("MQTT connecting to %s:%s", self.host, self.port)

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
        self._connected.clear()

    # -- publish / subscribe -------------------------------------------

    def subscribe(self, topic: str) -> None:
        self._client.subscribe(topic, qos=self.qos)

    def publish(self, topic: str, payload: str) -> None:
        self._client.publish(topic, payload, retain=self.retain, qos=self.qos)

    def publish_json(self, topic: str, payload: Dict[str, Any]) -> None:
        self.publish(topic, json.dumps(payload))

    def publish_availability(self, base_topic: Optional[str] = None, online: bool = True) -> None:
        """Publish retained availability.

        ``base_topic`` is kept for backward compatibility; when omitted the
        connection's own availability topic is used.
        """
        topic = (
            availability_topic_for(base_topic)
            if base_topic is not None
            else self.availability_topic
        )
        if topic is None:
            raise ValueError("No availability topic configured")
        payload = self.payload_available if online else self.payload_not_available
        self._client.publish(topic, payload, retain=True, qos=self.qos)

    # -- paho callbacks ------------------------------------------------

    def _on_connect(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _flags: object,
        reason_code: Any,
        _properties: object = None,
    ) -> None:
        if _is_failure(reason_code):
            log.warning("MQTT connect to %s:%s refused: %s", self.host, self.port, reason_code)
            return
        self._connected.set()
        log.info("MQTT connected to %s:%s", self.host, self.port)
        if self.availability_topic is not None:
            self.publish_availability(online=True)
        for callback in list(self._connect_callbacks):
            try:
                callback()
            except Exception:  # noqa: BLE001 - never kill the network thread
                log.exception("MQTT connect callback failed")

    def _on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _flags: object = None,
        reason_code: Any = None,
        _properties: object = None,
    ) -> None:
        self._connected.clear()
        log.info("MQTT disconnected from %s:%s (%s)", self.host, self.port, reason_code)

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


def _is_failure(reason_code: Any) -> bool:
    failure = getattr(reason_code, "is_failure", None)
    if failure is not None:
        return bool(failure)
    try:
        return int(reason_code) != 0
    except (TypeError, ValueError):
        return False
