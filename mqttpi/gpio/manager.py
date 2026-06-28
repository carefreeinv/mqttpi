"""GPIO pin manager — outputs, inputs, MQTT command handling."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from mqttpi.gpio.backend import GpioBackend, create_backend
from mqttpi.gpio.ha_mqtt import GpioMqttPublisher
from mqttpi.gpio.pins import PinConfig, parse_pins
from mqttpi.mqtt.client import MqttConnection

log = logging.getLogger(__name__)


class GpioManager:
    def __init__(
        self,
        cfg: Dict[str, Any],
        mqtt: MqttConnection,
        mock_gpio: bool = False,
    ) -> None:
        self.cfg = cfg
        self.mqtt = mqtt
        self.pins = parse_pins(cfg)
        if not self.pins:
            raise ValueError("No supported GPIO pins in config")

        mqtt_cfg = cfg.get("mqtt", {})
        device_cfg = cfg.get("device", {})
        ha_cfg = device_cfg.get("ha", {})
        device_id = str(device_cfg.get("id", "mqttpi-node"))

        self.publisher = GpioMqttPublisher(
            mqtt=mqtt,
            base_topic=str(mqtt_cfg.get("base_topic", f"mqttpi/{device_id}")),
            device_id=device_id,
            device_name=str(ha_cfg.get("name", device_id)),
            discovery_prefix=str(
                mqtt_cfg.get("homeassistant", {}).get("discovery_prefix", "homeassistant")
            ),
            payload_on=str(mqtt_cfg.get("payload_on", "ON")),
            payload_off=str(mqtt_cfg.get("payload_off", "OFF")),
            manufacturer=str(ha_cfg.get("manufacturer", "mqttpi")),
            model=str(ha_cfg.get("model", device_cfg.get("board", ""))),
        )
        self.backend: GpioBackend = create_backend(force_mock=mock_gpio)
        self._outputs: Dict[str, PinConfig] = {}
        self._inputs: Dict[str, PinConfig] = {}
        self._output_state: Dict[str, bool] = {}
        self._input_state: Dict[str, bool] = {}
        self._stop = threading.Event()
        self._input_thread: Optional[threading.Thread] = None

        for pin in self.pins:
            if pin.direction == "output":
                self._outputs[pin.alias] = pin
            else:
                self._inputs[pin.alias] = pin

    def start(self) -> None:
        for pin in self.pins:
            if pin.direction == "output":
                self.backend.setup_output(pin.pin, pin.initial)
                self._output_state[pin.alias] = pin.initial
            else:
                self.backend.setup_input(pin.pin, pin.pull)
                raw = self.backend.read(pin.pin)
                self._input_state[pin.alias] = self._logical_input(pin, raw)

        if mqtt_cfg_discovery := self.cfg.get("mqtt", {}).get("homeassistant", {}):
            if mqtt_cfg_discovery.get("discovery", True):
                self.publisher.publish_discovery(self.pins)

        for alias, on in self._output_state.items():
            self.publisher.publish_state(alias, on)
        for alias, on in self._input_state.items():
            self.publisher.publish_state(alias, on)

        for alias in self._outputs:
            topic = f"{self.publisher.base_topic}/gpio/{alias}/set"
            self.mqtt.subscribe(topic)

        if self._inputs:
            self._input_thread = threading.Thread(
                target=self._input_poll_loop,
                name="mqttpi-gpio-inputs",
                daemon=True,
            )
            self._input_thread.start()

        log.info(
            "GPIO started: %d outputs, %d inputs",
            len(self._outputs),
            len(self._inputs),
        )

    def handle_mqtt_message(self, topic: str, payload: str) -> None:
        prefix = f"{self.publisher.base_topic}/gpio/"
        if not topic.startswith(prefix) or not topic.endswith("/set"):
            return
        alias = topic[len(prefix) : -4]
        pin = self._outputs.get(alias)
        if pin is None:
            return

        on = payload == self.publisher.payload_on
        if payload not in (self.publisher.payload_on, self.publisher.payload_off):
            log.warning("Ignoring unknown payload %r on %s", payload, topic)
            return

        self.backend.write(pin.pin, on)
        self._output_state[alias] = on
        self.publisher.publish_state(alias, on)
        log.debug("Set %s → %s", alias, payload)

    def stop(self) -> None:
        self._stop.set()
        if self._input_thread is not None:
            self._input_thread.join(timeout=2)
        self.backend.cleanup()
        log.info("GPIO stopped")

    def _logical_input(self, pin: PinConfig, raw: bool) -> bool:
        value = raw
        if pin.invert:
            value = not value
        return value

    def _input_poll_loop(self) -> None:
        last_change: Dict[str, float] = {alias: 0.0 for alias in self._inputs}
        stable: Dict[str, bool] = dict(self._input_state)

        while not self._stop.is_set():
            now = time.monotonic()
            for alias, pin in self._inputs.items():
                raw = self.backend.read(pin.pin)
                logical = self._logical_input(pin, raw)
                debounce_s = pin.debounce_ms / 1000.0

                if logical != stable.get(alias, logical):
                    if now - last_change[alias] >= debounce_s:
                        stable[alias] = logical
                        self._input_state[alias] = logical
                        self.publisher.publish_state(alias, logical)
                        log.debug("Input %s → %s", alias, logical)
                    last_change[alias] = now

            self._stop.wait(0.02)