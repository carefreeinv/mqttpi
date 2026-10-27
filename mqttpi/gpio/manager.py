"""GPIO pin manager — outputs, inputs, MQTT command handling."""

from __future__ import annotations

import logging
import threading
import time
from types import MappingProxyType
from typing import Any, Dict, List, Optional

from mqttpi.gpio.backend import GpioBackend, create_backend
from mqttpi.gpio.commands import CommandFilter, CommandRequest, run_filters
from mqttpi.gpio.ha_mqtt import GpioMqttPublisher
from mqttpi.gpio.pins import PinConfig, parse_pins
from mqttpi.mqtt.client import MqttConnection
from mqttpi.mqtt.discovery import parse_discovery_layout

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
            layout=parse_discovery_layout(cfg),
        )
        gpio_cfg = cfg.get("gpio") or {}
        backend_choice = gpio_cfg.get("backend") if isinstance(gpio_cfg, dict) else None
        self.backend: GpioBackend = create_backend(
            force_mock=mock_gpio,
            backend=str(backend_choice) if backend_choice is not None else None,
        )
        #: Active backend name ("rpi" or "mock") for library users and logs.
        self.backend_name: str = self.backend.name
        log.info(
            "GPIO backend: %s (board: %s)",
            self.backend_name,
            device_cfg.get("board", "unspecified"),
        )
        self._outputs: Dict[str, PinConfig] = {}
        self._inputs: Dict[str, PinConfig] = {}
        self._output_state: Dict[str, bool] = {}
        self._input_state: Dict[str, bool] = {}
        self._stop = threading.Event()
        self._input_thread: Optional[threading.Thread] = None
        self._started = False
        self._announce_lock = threading.Lock()
        self._command_lock = threading.Lock()
        self._filters: List[CommandFilter] = []

        for pin in self.pins:
            if pin.direction == "output":
                self._outputs[pin.alias] = pin
            else:
                self._inputs[pin.alias] = pin

    def start(self) -> None:
        for pin in self.pins:
            if pin.direction == "output":
                # invert: true → active-low output (logical ON drives the pin LOW).
                self.backend.setup_output(pin.pin, pin.initial != pin.invert)
                self._output_state[pin.alias] = pin.initial
            else:
                self.backend.setup_input(pin.pin, pin.pull)
                raw = self.backend.read(pin.pin)
                self._input_state[pin.alias] = self._logical_input(pin, raw)

        for alias in self._outputs:
            topic = f"{self.publisher.base_topic}/gpio/{alias}/set"
            self.mqtt.subscribe(topic)  # re-issued by MqttConnection on reconnect

        self._started = True
        # Discovery and state are (re)published on every broker connect, so a
        # broker restarted without persistence gets them again.
        self.mqtt.add_connect_callback(self.announce)
        if self.mqtt.is_connected:
            self.announce()

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

    @property
    def discovery_enabled(self) -> bool:
        ha_cfg = self.cfg.get("mqtt", {}).get("homeassistant") or {}
        return bool(ha_cfg.get("discovery", True))

    def announce(self) -> None:
        """Publish HA discovery (if enabled) and every current pin state."""
        if not self._started:
            return
        with self._announce_lock:
            if self.discovery_enabled:
                self.publisher.publish_discovery(self.pins)
            for alias, on in list(self._output_state.items()):
                self.publisher.publish_state(alias, on)
            for alias, on in list(self._input_state.items()):
                self.publisher.publish_state(alias, on)

    def handle_mqtt_message(self, topic: str, payload: str) -> None:
        prefix = f"{self.publisher.base_topic}/gpio/"
        if not topic.startswith(prefix) or not topic.endswith("/set"):
            return
        alias = topic[len(prefix) : -4]
        pin = self._outputs.get(alias)
        if pin is None:
            return

        if payload not in (self.publisher.payload_on, self.publisher.payload_off):
            log.warning("Ignoring unknown payload %r on %s", payload, topic)
            return
        on = payload == self.publisher.payload_on
        self._apply_command(alias, on, source=topic, payload=payload)

    # --- command filters --------------------------------------------------

    def add_command_filter(self, command_filter: CommandFilter) -> None:
        """Register a filter run before every output change (see ``mqttpi.gpio.commands``)."""
        self._filters.append(command_filter)

    def remove_command_filter(self, command_filter: CommandFilter) -> None:
        self._filters.remove(command_filter)

    @property
    def command_filters(self) -> List[CommandFilter]:
        return list(self._filters)

    def states(self) -> Dict[str, bool]:
        """Snapshot of every output and input state, keyed by alias."""
        return {**self._input_state, **self._output_state}

    def request_output(self, alias: str, on: bool, source: str = "api") -> bool:
        """Set an output from code, through the same filters as MQTT commands.

        Returns the resulting output state. Raises ``KeyError`` for an unknown alias.
        """
        if alias not in self._outputs:
            raise KeyError(f"Unknown output alias {alias!r}")
        return self._apply_command(alias, bool(on), source=source)

    def _apply_command(self, alias: str, on: bool, source: str, payload: Optional[str] = None) -> bool:
        pin = self._outputs[alias]
        with self._command_lock:
            current = self._output_state.get(alias, False)
            if self._filters:
                request = CommandRequest(
                    alias=alias,
                    value=on,
                    current=current,
                    source=source,
                    payload=payload,
                    states=MappingProxyType(self.states()),
                )
                outcome = run_filters(self._filters, request)
                if not outcome.accepted:
                    log.info(
                        "Command %s → %s rejected: %s",
                        alias,
                        "ON" if on else "OFF",
                        "; ".join(outcome.reasons) or "rejected",
                    )
                    # Re-publish the true state so HA drops its optimistic toggle.
                    self.publisher.publish_state(alias, current)
                    return current
                if outcome.value != on:
                    log.info(
                        "Command %s → %s modified to %s: %s",
                        alias,
                        "ON" if on else "OFF",
                        "ON" if outcome.value else "OFF",
                        "; ".join(outcome.reasons) or "modified",
                    )
                on = bool(outcome.value)

            self.backend.write(pin.pin, on != pin.invert)
            self._output_state[alias] = on
        self.publisher.publish_state(alias, on)
        log.debug("Set %s → %s (%s)", alias, "ON" if on else "OFF", source)
        return on

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