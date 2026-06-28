"""Home Assistant MQTT discovery for GPIO entities."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from mqttpi.gpio.pins import PinConfig
from mqttpi.mqtt.client import MqttConnection

log = logging.getLogger(__name__)


class GpioMqttPublisher:
    def __init__(
        self,
        mqtt: MqttConnection,
        base_topic: str,
        device_id: str,
        device_name: str,
        discovery_prefix: str,
        payload_on: str,
        payload_off: str,
        manufacturer: str = "mqttpi",
        model: str = "",
    ) -> None:
        self.mqtt = mqtt
        self.base_topic = base_topic.rstrip("/")
        self.device_id = device_id
        self.device_name = device_name
        self.discovery_prefix = discovery_prefix
        self.payload_on = payload_on
        self.payload_off = payload_off
        self.manufacturer = manufacturer
        self.model = model

    def publish_discovery(self, pins: List[PinConfig]) -> None:
        device = self._device_block()
        for pin in pins:
            if pin.direction == "output":
                self._publish_switch_discovery(pin, device)
            elif pin.direction == "input":
                self._publish_binary_sensor_discovery(pin, device)
        log.info("Published HA discovery for %d GPIO entities", len(pins))

    def publish_state(self, alias: str, on: bool) -> None:
        payload = self.payload_on if on else self.payload_off
        self.mqtt.publish(self._state_topic(alias), payload)

    def _device_block(self) -> Dict[str, Any]:
        block: Dict[str, Any] = {
            "identifiers": [self.device_id],
            "name": self.device_name,
            "manufacturer": self.manufacturer,
        }
        if self.model:
            block["model"] = self.model
        return block

    def _state_topic(self, alias: str) -> str:
        return f"{self.base_topic}/gpio/{alias}/state"

    def _command_topic(self, alias: str) -> str:
        return f"{self.base_topic}/gpio/{alias}/set"

    def _discovery_topic(self, component: str, object_id: str) -> str:
        return f"{self.discovery_prefix}/{component}/{self.device_id}_{object_id}/config"

    def _publish_switch_discovery(self, pin: PinConfig, device: Dict[str, Any]) -> None:
        payload: Dict[str, Any] = {
            "name": pin.ha_name,
            "unique_id": f"{self.device_id}_{pin.alias}",
            "command_topic": self._command_topic(pin.alias),
            "state_topic": self._state_topic(pin.alias),
            "payload_on": self.payload_on,
            "payload_off": self.payload_off,
            "device": device,
        }
        if pin.ha_icon:
            payload["icon"] = pin.ha_icon
        self.mqtt.publish_json(self._discovery_topic("switch", pin.alias), payload)

    def _publish_binary_sensor_discovery(self, pin: PinConfig, device: Dict[str, Any]) -> None:
        payload: Dict[str, Any] = {
            "name": pin.ha_name,
            "unique_id": f"{self.device_id}_{pin.alias}",
            "state_topic": self._state_topic(pin.alias),
            "payload_on": self.payload_on,
            "payload_off": self.payload_off,
            "device": device,
        }
        if pin.ha_device_class:
            payload["device_class"] = pin.ha_device_class
        if pin.ha_icon:
            payload["icon"] = pin.ha_icon
        self.mqtt.publish_json(self._discovery_topic("binary_sensor", pin.alias), payload)