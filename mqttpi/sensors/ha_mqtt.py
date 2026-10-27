"""Home Assistant ``sensor`` entities for numeric readings.

Topics (under ``{base_topic}``, matching the documented examples):

* ``sensors/<alias>/state`` — the number, e.g. ``21.4``
* ``sensors/<alias>/attributes`` — JSON ``{"timestamp": ISO-8601, "quality": "good"}``
* ``sensors/<alias>/availability`` — ``online`` / ``offline`` (retained); goes
  ``offline`` when the sensor has had no good reading for ``stale_after_s``

Discovery uses ``availability_mode: all`` over the node status and the
entity's own availability topic, so an entity is shown unavailable when either
the node is down or its sensor is stale.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from mqttpi.mqtt.discovery import DiscoveryLayout
from mqttpi.sensors.model import EntitySpec, Reading

log = logging.getLogger(__name__)


class NumericSensorPublisher:
    def __init__(
        self,
        mqtt: Any,  # MqttConnection-compatible: publish(topic, payload, retain=None)
        base_topic: str,
        device_id: str,
        device: Dict[str, Any],
        layout: Optional[DiscoveryLayout] = None,
        node_availability_topic: Optional[str] = None,
        payload_available: str = "online",
        payload_not_available: str = "offline",
    ) -> None:
        self.mqtt = mqtt
        self.base_topic = base_topic.rstrip("/")
        self.device_id = device_id
        self.device = device
        self.layout = layout or DiscoveryLayout()
        self.node_availability_topic = node_availability_topic or f"{self.base_topic}/status"
        self.payload_available = payload_available
        self.payload_not_available = payload_not_available

    # topics
    def state_topic(self, alias: str) -> str:
        return f"{self.base_topic}/sensors/{alias}/state"

    def attributes_topic(self, alias: str) -> str:
        return f"{self.base_topic}/sensors/{alias}/attributes"

    def availability_topic(self, alias: str) -> str:
        return f"{self.base_topic}/sensors/{alias}/availability"

    # discovery
    def discovery_payload(self, e: EntitySpec) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": e.name,
            "unique_id": f"{self.device_id}_{e.alias}",
            "state_topic": self.state_topic(e.alias),
            "json_attributes_topic": self.attributes_topic(e.alias),
            "availability": [
                {"topic": self.node_availability_topic},
                {"topic": self.availability_topic(e.alias)},
            ],
            "availability_mode": "all",
            "payload_available": self.payload_available,
            "payload_not_available": self.payload_not_available,
            "device": self.device,
        }
        if e.unit:
            payload["unit_of_measurement"] = e.unit
        if e.device_class:
            payload["device_class"] = e.device_class
        if e.state_class:
            payload["state_class"] = e.state_class
        if e.icon:
            payload["icon"] = e.icon
        if e.precision is not None:
            payload["suggested_display_precision"] = e.precision
        for key, value in e.extra.items():
            payload.setdefault(key, value)
        return payload

    def discovery_topic(self, e: EntitySpec) -> str:
        return self.layout.topic("sensor", self.device_id, e.alias)

    def publish_discovery(self, entities: Iterable[EntitySpec]) -> None:
        n = 0
        for e in entities:
            for stale in self.layout.stale_topics("sensor", self.device_id, e.alias):
                self.mqtt.publish(stale, "", retain=True)
            self.mqtt.publish(self.discovery_topic(e), json.dumps(self.discovery_payload(e)), retain=True)
            n += 1
        log.info("Published HA discovery for %d sensor entities", n)

    # state
    def publish_reading(self, e: EntitySpec, value: float, reading: Reading) -> None:
        self.mqtt.publish(self.state_topic(e.alias), e.format(value), retain=e.retain)
        attrs = {
            "timestamp": datetime.fromtimestamp(reading.timestamp, timezone.utc).isoformat(timespec="seconds"),
            "quality": reading.quality,
        }
        self.mqtt.publish(self.attributes_topic(e.alias), json.dumps(attrs), retain=e.retain)

    def publish_availability(self, e: EntitySpec, online: bool) -> None:
        payload = self.payload_available if online else self.payload_not_available
        self.mqtt.publish(self.availability_topic(e.alias), payload, retain=True)
