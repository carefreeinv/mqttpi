"""Home Assistant MQTT discovery for JBD BMS (mqttpi topic layout)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

import paho.mqtt.client as mqtt

from mqttpi.bms.jbd_protocol import BmsData

log = logging.getLogger(__name__)


class BmsMqttPublisher:
    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: str = "",
        password: str = "",
        base_topic: str = "mqttpi/bms-node",
        client_id: str = "mqttpi-bms",
        device_name: str = "LiFePO4 Battery",
        device_id: str = "jbd_bms",
        discovery_prefix: str = "homeassistant",
        retain: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.base_topic = base_topic.rstrip("/")
        self.client_id = client_id
        self.device_name = device_name
        self.device_id = device_id
        self.discovery_prefix = discovery_prefix
        self.retain = retain
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
        )
        if username:
            self._client.username_pw_set(username, password or None)
        self._discovery_done = False

    def connect(self) -> None:
        self._client.connect(self.host, self.port, keepalive=60)
        self._client.loop_start()
        log.info("MQTT connected to %s:%s", self.host, self.port)

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

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
        return f"{self.discovery_prefix}/{component}/{self.device_id}_{object_id}/config"

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
            self._client.publish(self._state_topic(key), str(value), retain=self.retain)

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
        self._client.publish(
            f"{self.base_topic}/bms/state",
            json.dumps(summary),
            retain=self.retain,
        )

    def _publish_availability(self, online: bool) -> None:
        payload = "online" if online else "offline"
        self._client.publish(f"{self.base_topic}/status", payload, retain=self.retain)

    def _publish_json(self, topic: str, payload: Dict[str, Any]) -> None:
        self._client.publish(topic, json.dumps(payload), retain=self.retain)