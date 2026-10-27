"""Build an :class:`MqttConnection` from a mqttpi config mapping."""

from __future__ import annotations

from typing import Any, Dict, Optional

from mqttpi.config import mqtt_port, parse_tls
from mqttpi.mqtt.client import (
    DEFAULT_MAX_QUEUED_MESSAGES,
    DEFAULT_RECONNECT_MAX_S,
    DEFAULT_RECONNECT_MIN_S,
    MqttConnection,
)


def default_client_id(cfg: Dict[str, Any]) -> str:
    device_id = str(cfg.get("device", {}).get("id", "mqttpi-node"))
    return str(cfg.get("mqtt", {}).get("client_id", f"mqttpi-{device_id}"))


def build_mqtt(cfg: Dict[str, Any], client_id: Optional[str] = None) -> MqttConnection:
    """Connection for the daemon (or, with ``client_id``, another process)."""
    mqtt_cfg = cfg.get("mqtt", {})
    tls = parse_tls(mqtt_cfg.get("tls"))
    return MqttConnection(
        host=str(mqtt_cfg.get("host", "localhost")),
        port=mqtt_port(mqtt_cfg, tls),
        tls=tls,
        username=str(mqtt_cfg.get("username", "")),
        password=str(mqtt_cfg.get("password", "")),
        client_id=client_id or default_client_id(cfg),
        retain=bool(mqtt_cfg.get("retain", True)),
        qos=int(mqtt_cfg.get("qos", 1)),
        base_topic=base_topic_from(cfg),
        keepalive=int(mqtt_cfg.get("keepalive", 60)),
        reconnect_min_s=int(mqtt_cfg.get("reconnect_min_s", DEFAULT_RECONNECT_MIN_S)),
        reconnect_max_s=int(mqtt_cfg.get("reconnect_max_s", DEFAULT_RECONNECT_MAX_S)),
        max_queued_messages=int(
            mqtt_cfg.get("max_queued_messages", DEFAULT_MAX_QUEUED_MESSAGES)
        ),
    )


def base_topic_from(cfg: Dict[str, Any]) -> str:
    """Resolve ``mqtt.base_topic`` (default ``mqttpi/{device.id}``, as documented)."""
    device_id = str(cfg.get("device", {}).get("id", "mqttpi-node"))
    return str(cfg.get("mqtt", {}).get("base_topic", f"mqttpi/{device_id}"))
