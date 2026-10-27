"""Home Assistant MQTT discovery for JBD BMS (mqttpi topic layout)."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Protocol

from mqttpi.bms.jbd_protocol import BmsData
from mqttpi.config import TlsSettings
from mqttpi.mqtt.client import MqttConnection, availability_topic_for
from mqttpi.mqtt.discovery import DiscoveryLayout

log = logging.getLogger(__name__)


class MqttPublisher(Protocol):
    """The slice of :class:`~mqttpi.mqtt.client.MqttConnection` the BMS needs."""

    def publish(self, topic: str, payload: str, retain: Optional[bool] = None) -> None: ...

    def add_connect_callback(self, callback: Callable[[], None]) -> None: ...


class BmsMqttPublisher:
    """Publishes JBD BMS data and HA discovery.

    Two modes:

    * **Shared** (unified daemon): pass ``connection=`` — the daemon's
      :class:`MqttConnection`. One client id, one Last Will, one ``{base}/status``.
      BMS health goes to ``{base}/bms/status`` so a BMS read failure does not
      mark the whole node (GPIO entities) unavailable. ``connect()`` /
      ``disconnect()`` are no-ops; the daemon owns the connection.
    * **Standalone** (``mqttpi-bms``): pass broker settings (or a connection
      with ``owns_connection=True``); the publisher owns an
      :class:`MqttConnection` with Last Will and background reconnect, and
      BMS health is the node availability ``{base}/status`` as before.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1883,
        username: str = "",
        password: str = "",
        base_topic: str = "mqttpi/bms-node",
        client_id: str = "mqttpi-bms",
        device_name: str = "LiFePO4 Battery",
        device_id: str = "jbd_bms",
        discovery_prefix: str = "homeassistant",
        retain: bool = True,
        tls: Optional[TlsSettings] = None,
        connection: Optional[MqttPublisher] = None,
        owns_connection: bool = False,
        layout: Optional[DiscoveryLayout] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.base_topic = base_topic.rstrip("/")
        self.client_id = client_id
        self.device_name = device_name
        self.device_id = device_id
        self.discovery_prefix = discovery_prefix
        self.layout = layout or DiscoveryLayout(prefix=discovery_prefix)
        self.retain = retain
        self.tls = tls
        self.node_status_topic = availability_topic_for(self.base_topic)
        self._owns_connection = connection is None or owns_connection
        if connection is None:
            connection = MqttConnection(
                host=host,
                port=port,
                username=username,
                password=password,
                client_id=client_id,
                retain=retain,
                base_topic=self.base_topic,
                tls=tls,
            )
        if self._owns_connection:
            self.status_topic = self.node_status_topic
        else:
            self.status_topic = f"{self.base_topic}/bms/status"
        self._conn = connection
        self._discovery_done = False
        self._conn.add_connect_callback(self._on_connect)

    @property
    def shared(self) -> bool:
        return not self._owns_connection

    @property
    def connection(self) -> MqttPublisher:
        return self._conn

    def connect(self, blocking: bool = False, timeout: float = 10.0) -> None:
        """Connect an owned connection (no-op when shared).

        Non-blocking by default: retries in the background so polling keeps
        running while the broker is down. ``blocking=True`` waits up to
        ``timeout`` seconds and raises ``RuntimeError`` if the broker does not
        answer (fail-fast for ``--once``).
        """
        if not self._owns_connection:
            return
        conn = self._conn
        assert isinstance(conn, MqttConnection)
        conn.connect()
        if blocking and not conn.wait_connected(timeout):
            conn.disconnect()
            raise RuntimeError(f"MQTT broker {self.host}:{self.port} not reachable within {timeout:.0f}s")

    def _on_connect(self) -> None:
        # Re-send discovery on the next publish after every (re)connect, so a
        # broker restarted without persistence learns the entities again.
        self._discovery_done = False

    def disconnect(self) -> None:
        if self._owns_connection:
            conn = self._conn
            assert isinstance(conn, MqttConnection)
            conn.disconnect()

    def publish(self, data: BmsData, connection: str) -> None:
        if not self._discovery_done:
            self._publish_discovery(data.cell_count or 8, connection)
            self._discovery_done = True
        self._publish_state(data)
        self._publish_availability(True)

    def publish_offline(self) -> None:
        self._publish_availability(False)

    def _device_block(self, connection: str) -> Dict[str, Any]:
        return {
            "identifiers": [self.device_id],
            "name": self.device_name,
            "manufacturer": "JBD / Jiabaida",
            "model": "JBD BMS",
            "connections": [["serial", connection]],
        }

    def _discovery_topic(self, component: str, object_id: str) -> str:
        for stale in self.layout.stale_topics(component, self.device_id, object_id):
            self._conn.publish(stale, "", retain=True)
        return self.layout.topic(component, self.device_id, object_id)

    def _state_topic(self, key: str) -> str:
        return f"{self.base_topic}/bms/{key}/state"

    def _publish_discovery(self, cell_count: int, connection: str) -> None:
        device = self._device_block(connection)
        sensors: List[Dict[str, Any]] = [
            {
                "object_id": "total_voltage",
                "name": "Total Voltage",
                "key": "total_voltage",
                "unit": "V",
                "device_class": "voltage",
                "state_class": "measurement",
                "icon": "battery",
                "precision": 2,
            },
            {
                "object_id": "current",
                "name": "Current",
                "key": "current",
                "unit": "A",
                "device_class": "current",
                "state_class": "measurement",
                "icon": "current-dc",
                "precision": 2,
            },
            {
                "object_id": "power",
                "name": "Power",
                "key": "power",
                "unit": "W",
                "device_class": "power",
                "state_class": "measurement",
                "precision": 1,
            },
            {
                "object_id": "soc",
                "name": "State of Charge",
                "key": "soc",
                "unit": "%",
                "device_class": "battery",
                "state_class": "measurement",
                "icon": "battery-charging",
            },
            {
                "object_id": "capacity_remaining",
                "name": "Capacity Remaining",
                "key": "capacity_remaining_ah",
                "unit": "Ah",
                "device_class": "energy_storage",
                "state_class": "measurement",
                "precision": 2,
            },
            {
                "object_id": "nominal_capacity",
                "name": "Nominal Capacity",
                "key": "nominal_capacity_ah",
                "unit": "Ah",
                "device_class": "energy_storage",
                "state_class": "measurement",
                "precision": 2,
            },
            {
                "object_id": "cycle_count",
                "name": "Cycle Count",
                "key": "cycle_count",
                "state_class": "total_increasing",
                "icon": "counter",
            },
            {
                "object_id": "min_cell_voltage",
                "name": "Min Cell Voltage",
                "key": "min_cell_voltage",
                "unit": "V",
                "device_class": "voltage",
                "state_class": "measurement",
                "precision": 3,
            },
            {
                "object_id": "max_cell_voltage",
                "name": "Max Cell Voltage",
                "key": "max_cell_voltage",
                "unit": "V",
                "device_class": "voltage",
                "state_class": "measurement",
                "precision": 3,
            },
            {
                "object_id": "delta_cell_voltage",
                "name": "Cell Voltage Delta",
                "key": "delta_cell_voltage",
                "unit": "V",
                "device_class": "voltage",
                "state_class": "measurement",
                "precision": 3,
            },
            {
                "object_id": "avg_cell_voltage",
                "name": "Average Cell Voltage",
                "key": "avg_cell_voltage",
                "unit": "V",
                "device_class": "voltage",
                "state_class": "measurement",
                "precision": 3,
            },
        ]

        for i in range(1, cell_count + 1):
            sensors.append(
                {
                    "object_id": f"cell_{i}_voltage",
                    "name": f"Cell {i} Voltage",
                    "key": f"cell_{i}",
                    "unit": "V",
                    "device_class": "voltage",
                    "state_class": "measurement",
                    "precision": 3,
                }
            )

        for i in range(1, 4):
            sensors.append(
                {
                    "object_id": f"temperature_{i}",
                    "name": f"Temperature {i}",
                    "key": f"temperature_{i}",
                    "unit": "°C",
                    "device_class": "temperature",
                    "state_class": "measurement",
                    "precision": 1,
                }
            )

        binary_sensors = [
            ("charging", "Charging", "battery_charging"),
            ("discharging", "Discharging", "battery-arrow-down"),
            ("balancing", "Balancing", "scale-balance"),
            ("protection_active", "Protection Active", "shield-alert"),
        ]

        for spec in sensors:
            payload = {
                "name": f"{self.device_name} {spec['name']}",
                "unique_id": f"{self.device_id}_{spec['object_id']}",
                "state_topic": self._state_topic(spec["key"]),
                "device": device,
                **self._availability(),
            }
            if "unit" in spec:
                payload["unit_of_measurement"] = spec["unit"]
            if "device_class" in spec:
                payload["device_class"] = spec["device_class"]
            if "state_class" in spec:
                payload["state_class"] = spec["state_class"]
            if "icon" in spec:
                payload["icon"] = f"mdi:{spec['icon']}"
            self._publish_json(self._discovery_topic("sensor", spec["object_id"]), payload)

        for key, name, icon in binary_sensors:
            payload = {
                "name": f"{self.device_name} {name}",
                "unique_id": f"{self.device_id}_{key}",
                "state_topic": self._state_topic(key),
                "device": device,
                **self._availability(),
                "payload_on": "ON",
                "payload_off": "OFF",
                "icon": f"mdi:{icon}",
            }
            self._publish_json(self._discovery_topic("binary_sensor", key), payload)

        text_payload = {
            "name": f"{self.device_name} Protection Flags",
            "unique_id": f"{self.device_id}_protection_flags",
            "state_topic": self._state_topic("protection_flags"),
            "device": device,
            **self._availability(),
            "icon": "mdi:alert-circle-outline",
        }
        self._publish_json(self._discovery_topic("sensor", "protection_flags"), text_payload)
        log.info("Published HA discovery for %d cells", cell_count)

    def _publish_state(self, data: BmsData) -> None:
        values: Dict[str, Any] = {
            "total_voltage": round(data.total_voltage, 2),
            "current": round(data.current, 2),
            "power": round(data.power, 1),
            "soc": data.soc,
            "capacity_remaining_ah": round(data.capacity_remaining_ah, 2),
            "nominal_capacity_ah": round(data.nominal_capacity_ah, 2),
            "cycle_count": data.cycle_count,
            "min_cell_voltage": round(data.min_cell_voltage, 3),
            "max_cell_voltage": round(data.max_cell_voltage, 3),
            "delta_cell_voltage": round(data.delta_cell_voltage, 3),
            "avg_cell_voltage": round(data.avg_cell_voltage, 3),
            "charging": "ON" if data.charging else "OFF",
            "discharging": "ON" if data.discharging else "OFF",
            "balancing": "ON" if data.balancing else "OFF",
            "protection_active": "ON" if data.protection_active else "OFF",
            "protection_flags": data.protection_flags,
        }
        for i, voltage in enumerate(data.cell_voltages, start=1):
            values[f"cell_{i}"] = round(voltage, 3)
        for i, temp in enumerate(data.temperatures_c, start=1):
            values[f"temperature_{i}"] = round(temp, 1)

        for key, value in values.items():
            self._conn.publish(self._state_topic(key), str(value))

        summary = {
            "soc": data.soc,
            "total_voltage": data.total_voltage,
            "current": data.current,
            "power": data.power,
            "cell_voltages": data.cell_voltages,
            "temperatures_c": data.temperatures_c,
            "protection_flags": data.protection_flags,
            "balancing_cells": data.balancing_cells,
        }
        self._conn.publish(f"{self.base_topic}/bms/state", json.dumps(summary))

    def _publish_availability(self, online: bool) -> None:
        self._conn.publish(self.status_topic, "online" if online else "offline")

    def _availability(self) -> Dict[str, Any]:
        if self.status_topic == self.node_status_topic:
            return {"availability_topic": self.node_status_topic}
        # Shared mode: unavailable when the node is offline OR the BMS is failing.
        return {
            "availability": [
                {"topic": self.node_status_topic},
                {"topic": self.status_topic},
            ],
            "availability_mode": "all",
        }

    def _publish_json(self, topic: str, payload: Dict[str, Any]) -> None:
        self._conn.publish(topic, json.dumps(payload))