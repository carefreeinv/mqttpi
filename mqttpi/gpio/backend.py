"""GPIO backends for mqttpi (RPi.GPIO on Linux Pi, mock for tests)."""

from __future__ import annotations

import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)


class GpioBackend:
    def setup_output(self, pin: int, initial: bool) -> None:
        raise NotImplementedError

    def setup_input(self, pin: int, pull: Optional[str]) -> None:
        raise NotImplementedError

    def write(self, pin: int, value: bool) -> None:
        raise NotImplementedError

    def read(self, pin: int) -> bool:
        raise NotImplementedError

    def cleanup(self) -> None:
        pass


class MockGpioBackend(GpioBackend):
    def __init__(self) -> None:
        self._values: Dict[int, bool] = {}

    def setup_output(self, pin: int, initial: bool) -> None:
        self._values[pin] = initial

    def setup_input(self, pin: int, pull: Optional[str]) -> None:
        self._values.setdefault(pin, False)

    def write(self, pin: int, value: bool) -> None:
        self._values[pin] = value

    def read(self, pin: int) -> bool:
        return self._values.get(pin, False)

    def cleanup(self) -> None:
        self._values.clear()


class RPiGpioBackend(GpioBackend):
    def __init__(self) -> None:
        import RPi.GPIO as GPIO

        self._gpio = GPIO
        self._gpio.setmode(GPIO.BCM)
        self._gpio.setwarnings(False)
        self._pull_map = {
            None: GPIO.PUD_OFF,
            "up": GPIO.PUD_UP,
            "down": GPIO.PUD_DOWN,
        }

    def setup_output(self, pin: int, initial: bool) -> None:
        self._gpio.setup(pin, self._gpio.OUT, initial=self._gpio.HIGH if initial else self._gpio.LOW)

    def setup_input(self, pin: int, pull: Optional[str]) -> None:
        self._gpio.setup(pin, self._gpio.IN, pull_up_down=self._pull_map.get(pull, self._gpio.PUD_OFF))

    def write(self, pin: int, value: bool) -> None:
        self._gpio.output(pin, self._gpio.HIGH if value else self._gpio.LOW)

    def read(self, pin: int) -> bool:
        return bool(self._gpio.input(pin))

    def cleanup(self) -> None:
        self._gpio.cleanup()


def create_backend(force_mock: bool = False) -> GpioBackend:
    if force_mock:
        log.info("Using mock GPIO backend")
        return MockGpioBackend()
    try:
        return RPiGpioBackend()
    except (ImportError, RuntimeError) as exc:
        log.warning("RPi.GPIO unavailable (%s) — using mock GPIO backend", exc)
        return MockGpioBackend()