"""Sensor subsystem: config -> drivers -> scheduler -> HA sensor entities."""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

from mqttpi.mqtt.discovery import parse_discovery_layout
from mqttpi.mqtt.factory import base_topic_from
from mqttpi.sensors.config import SensorConfig, parse_sensors
from mqttpi.sensors.ha_mqtt import NumericSensorPublisher
from mqttpi.sensors.model import EntitySpec, Reading, SensorDriver
from mqttpi.sensors.scheduler import ScheduledSensor, SensorScheduler

log = logging.getLogger(__name__)


def node_device_block(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Same HA device block as the GPIO entities, so all appear on one device."""
    device_cfg = cfg.get("device", {}) or {}
    ha_cfg = device_cfg.get("ha", {}) or {}
    device_id = str(device_cfg.get("id", "mqttpi-node"))
    block: Dict[str, Any] = {
        "identifiers": [device_id],
        "name": str(ha_cfg.get("name", device_id)),
        "manufacturer": str(ha_cfg.get("manufacturer", "mqttpi")),
    }
    model = str(ha_cfg.get("model", device_cfg.get("board", "")))
    if model:
        block["model"] = model
    return block


class SensorSubsystem:
    def __init__(
        self,
        cfg: Dict[str, Any],
        connection: Any,
        sensors: Optional[List[Tuple[SensorConfig, SensorDriver]]] = None,
        clock: Any = None,
    ) -> None:
        self.cfg = cfg
        self.mqtt = connection
        self.sensors = sensors if sensors is not None else parse_sensors(cfg)
        if not self.sensors:
            raise ValueError("No sensors with an available driver in config")
        device_id = str((cfg.get("device") or {}).get("id", "mqttpi-node"))
        base_topic = getattr(connection, "base_topic", None) or base_topic_from(cfg)
        self.publisher = NumericSensorPublisher(
            mqtt=connection,
            base_topic=base_topic,
            device_id=device_id,
            device=node_device_block(cfg),
            layout=parse_discovery_layout(cfg),
            node_availability_topic=getattr(connection, "availability_topic", None) or f"{base_topic}/status",
            payload_available=str(getattr(connection, "payload_available", "online")),
            payload_not_available=str(getattr(connection, "payload_not_available", "offline")),
        )
        self._entities: Dict[str, List[EntitySpec]] = {sc.name: sc.entities for sc, _ in self.sensors}
        self._lock = threading.Lock()
        self._online: Dict[str, bool] = {sc.name: False for sc, _ in self.sensors}
        self._last: Dict[str, Tuple[Reading, Dict[str, float]]] = {}
        kwargs = {"clock": clock} if clock is not None else {}
        self.scheduler = SensorScheduler(
            [
                ScheduledSensor(sc.name, drv, sc.interval_s, sc.timeout_s, sc.stale_after_s)
                for sc, drv in self.sensors
            ],
            on_reading=self._on_reading,
            on_stale=self._on_stale,
            **kwargs,
        )

    @property
    def entities(self) -> List[EntitySpec]:
        return [e for es in self._entities.values() for e in es]

    def start(self) -> None:
        self.mqtt.add_connect_callback(self.announce)
        if self.mqtt.is_connected:
            self.announce()
        self.scheduler.start()
        log.info("Sensors started: %d sensors, %d entities", len(self.sensors), len(self.entities))

    def stop(self) -> None:
        self.scheduler.stop()
        for _sc, drv in self.sensors:
            close = getattr(drv, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # pragma: no cover
                    log.debug("Sensor driver close failed", exc_info=True)

    def announce(self) -> None:
        """(Re)publish discovery, per-entity availability and last values."""
        with self._lock:
            self.publisher.publish_discovery(self.entities)
            for name, entities in self._entities.items():
                for e in entities:
                    self.publisher.publish_availability(e, self._online[name])
                if self._online[name] and name in self._last:
                    reading, values = self._last[name]
                    self._publish_values(name, reading, values)

    def _on_reading(self, s: ScheduledSensor, reading: Reading) -> None:
        values = reading.numeric()
        with self._lock:
            self._last[s.name] = (reading, values)
            self._publish_values(s.name, reading, values)
            if not self._online[s.name]:
                self._online[s.name] = True
                for e in self._entities[s.name]:
                    self.publisher.publish_availability(e, True)

    def _publish_values(self, name: str, reading: Reading, values: Dict[str, float]) -> None:
        for e in self._entities[name]:
            if e.key in values:
                self.publisher.publish_reading(e, values[e.key], reading)

    def _on_stale(self, s: ScheduledSensor) -> None:
        with self._lock:
            self._online[s.name] = False
            for e in self._entities[s.name]:
                self.publisher.publish_availability(e, False)
