"""Shared MQTT connection for mqttpi subsystems."""

from __future__ import annotations

import json
import logging
import ssl
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

import paho.mqtt.client as mqtt

from mqttpi.config import TlsSettings

log = logging.getLogger(__name__)

PAYLOAD_AVAILABLE = "online"
PAYLOAD_NOT_AVAILABLE = "offline"

DEFAULT_RECONNECT_MIN_S = 1
DEFAULT_RECONNECT_MAX_S = 60
DEFAULT_MAX_QUEUED_MESSAGES = 1000
# After this many consecutive failed attempts, log one more warning so a
# misconfigured broker target is visible without spamming the log.
WARN_AFTER_FAILED_ATTEMPTS = 10

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

    ``connect()`` never blocks and never raises because the broker is
    unreachable: paho retries in the background with exponential backoff
    between ``reconnect_min_s`` and ``reconnect_max_s``. Subscriptions made
    with :meth:`subscribe` are remembered and re-issued after every reconnect.
    While disconnected, qos>0 publishes are queued up to
    ``max_queued_messages`` (newest messages are dropped once the queue is
    full; qos 0 publishes are dropped). Use :meth:`wait_connected` if you
    need to block until the first connection.
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
        reconnect_min_s: int = DEFAULT_RECONNECT_MIN_S,
        reconnect_max_s: int = DEFAULT_RECONNECT_MAX_S,
        max_queued_messages: int = DEFAULT_MAX_QUEUED_MESSAGES,
        tls: Optional[TlsSettings] = None,
    ) -> None:
        _validate_target(host, port)
        if reconnect_min_s < 1 or reconnect_max_s < reconnect_min_s:
            raise ValueError(
                "mqtt.reconnect_min_s must be >= 1 and <= mqtt.reconnect_max_s "
                f"(got {reconnect_min_s}, {reconnect_max_s})"
            )
        if max_queued_messages < 0:
            raise ValueError("mqtt.max_queued_messages must be >= 0 (0 = unbounded)")
        self.host = host
        self.port = port
        self.tls = tls
        self.username = username
        self.password = password
        self.client_id = client_id
        self.retain = retain
        self.qos = qos
        self.keepalive = int(keepalive)
        self.base_topic = base_topic.rstrip("/") if base_topic else None
        if availability_topic is None and base_topic is not None:
            availability_topic = availability_topic_for(base_topic)
        self.availability_topic = availability_topic
        self.will_enabled = bool(will and availability_topic)
        self.payload_available = payload_available
        self.payload_not_available = payload_not_available
        self.reconnect_min_s = int(reconnect_min_s)
        self.reconnect_max_s = int(reconnect_max_s)
        self.max_queued_messages = int(max_queued_messages)

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
        )
        if username:
            self._client.username_pw_set(username, password or None)
        self._message_handler: Optional[Callable[[str, str], None]] = None
        self._connect_callbacks: List[ConnectCallback] = []
        self._connected = threading.Event()
        self._subscriptions: List[str] = []
        self._lock = threading.Lock()
        self._failed_attempts = 0
        self._outage_logged = False
        self._client.on_message = self._on_message
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_connect_fail = self._on_connect_fail
        if tls is not None:
            # Done up front so bad certificate files fail fast (ValueError).
            apply_tls(self._client, tls)

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

    def wait_connected(self, timeout: Optional[float] = None) -> bool:
        """Block until connected (or ``timeout`` seconds). Returns ``is_connected``."""
        return self._connected.wait(timeout)

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
        self._client.reconnect_delay_set(self.reconnect_min_s, self.reconnect_max_s)
        self._client.max_queued_messages_set(self.max_queued_messages)
        # Non-blocking: DNS lookup and TCP connect happen on the network
        # thread, which keeps retrying with backoff until the broker answers.
        self._client.connect_async(self.host, self.port, keepalive=self.keepalive)
        self._client.loop_start()
        log.info(
            "MQTT connecting to %s:%s over %s in background (retry %s-%ss)",
            self.host,
            self.port,
            self.transport,
            self.reconnect_min_s,
            self.reconnect_max_s,
        )

    @property
    def transport(self) -> str:
        """Human-readable transport, e.g. ``TLS (system CA store)`` or ``plain TCP``."""
        return f"TLS ({self.tls.describe()})" if self.tls is not None else "plain TCP"

    def disconnect(self) -> None:
        # disconnect() first: the network thread flushes queued messages
        # (e.g. the final "offline") before sending DISCONNECT, then exits.
        self._client.disconnect()
        self._client.loop_stop()
        self._connected.clear()

    # -- publish / subscribe -------------------------------------------

    def subscribe(self, topic: str) -> None:
        """Subscribe now if connected, and again after every reconnect."""
        with self._lock:
            if topic not in self._subscriptions:
                self._subscriptions.append(topic)
        if self.is_connected:
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
        if self._outage_logged:
            log.info(
                "MQTT reconnected to %s:%s after %d failed attempt(s)",
                self.host,
                self.port,
                self._failed_attempts,
            )
        else:
            log.info("MQTT connected to %s:%s", self.host, self.port)
        self._failed_attempts = 0
        self._outage_logged = False
        with self._lock:
            topics = list(self._subscriptions)
        for topic in topics:
            self._client.subscribe(topic, qos=self.qos)
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
        was_connected = self._connected.is_set()
        self._connected.clear()
        if was_connected and _is_failure(reason_code):
            self._note_outage(f"connection lost ({reason_code})")
        else:
            log.info("MQTT disconnected from %s:%s (%s)", self.host, self.port, reason_code)

    def _on_connect_fail(self, _client: mqtt.Client, _userdata: object) -> None:
        self._failed_attempts += 1
        # paho calls this from inside its ``except OSError`` block, so the
        # failure (refused, DNS, TLS handshake, ...) is still available here.
        exc = sys.exc_info()[1]
        if isinstance(exc, ssl.SSLError):
            reason = (
                f"TLS handshake failed ({exc}) — check mqtt.tls.ca_certs, the broker "
                "certificate (expiry, hostname), and the system clock"
            )
        elif exc is not None:
            reason = f"unreachable ({exc})"
        else:
            reason = "broker unreachable"
        self._note_outage(reason)
        if self._failed_attempts == WARN_AFTER_FAILED_ATTEMPTS:
            log.warning(
                "MQTT still not connected to %s:%s after %d attempts — check mqtt.host / mqtt.port",
                self.host,
                self.port,
                self._failed_attempts,
            )

    def _note_outage(self, reason: str) -> None:
        """Log one warning per outage; further retries log at debug level."""
        if self._outage_logged:
            log.debug("MQTT %s:%s retry failed: %s", self.host, self.port, reason)
            return
        self._outage_logged = True
        log.warning(
            "MQTT %s:%s %s — retrying in background (local work continues)",
            self.host,
            self.port,
            reason,
        )

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


def apply_tls(client: Any, tls: TlsSettings) -> None:
    """Configure a paho client for TLS (CA verification always on)."""
    try:
        client.tls_set(
            ca_certs=tls.ca_certs,
            certfile=tls.certfile,
            keyfile=tls.keyfile,
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
    except (ssl.SSLError, OSError) as exc:
        # Bad PEM / wrong key: a configuration error, fail fast. The message
        # names files only — never key material.
        raise ValueError(f"mqtt.tls: cannot load certificates ({tls.describe()}): {exc}") from exc
    if tls.insecure:
        client.tls_insecure_set(True)
        log.warning(
            "mqtt.tls.insecure is on: broker hostname is NOT verified "
            "(certificate chain still is). Use only on a lab network."
        )


def _validate_target(host: str, port: int) -> None:
    """Fail fast on configuration errors (not on an unreachable broker)."""
    if not isinstance(host, str) or not host.strip():
        raise ValueError("mqtt.host must be a non-empty hostname or IP address")
    if any(ch.isspace() for ch in host) or "/" in host:
        raise ValueError(f"mqtt.host {host!r} is not a valid hostname or IP address")
    if not 0 < int(port) < 65536:
        raise ValueError(f"mqtt.port must be 1-65535 (got {port})")


def _is_failure(reason_code: Any) -> bool:
    failure = getattr(reason_code, "is_failure", None)
    if failure is not None:
        return bool(failure)
    try:
        return int(reason_code) != 0
    except (TypeError, ValueError):
        return False
