"""GPIO backends for mqttpi (RPi.GPIO on Linux Pi, mock for tests)."""

from __future__ import annotations

import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)


class GpioBackendUnavailable(RuntimeError):
    """Raised when the hardware GPIO backend cannot be loaded or initialised."""


class GpioBackend:
    #: Short name of the backend, logged at startup ("rpi", "mock", ...).
    name = "unknown"

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
    name = "mock"

    def __init__(self) -> None:
        self._values: Dict[int, bool] = {}

    def setup_output(self, pin: int, initial: bool) -> None:
        self._values[pin] = initial

    def setup_input(self, pin: int, pull: Optional[str]) -> None:
        # Idle level follows the pull resistor, like an unconnected real pin.
        self._values.setdefault(pin, pull == "up")

    def write(self, pin: int, value: bool) -> None:
        self._values[pin] = value

    def read(self, pin: int) -> bool:
        return self._values.get(pin, False)

    def cleanup(self) -> None:
        self._values.clear()


class RPiGpioBackend(GpioBackend):
    name = "rpi"

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


BACKEND_CHOICES = ("rpi", "mock")

_HINT = (
    "Install the GPIO library (pip install -r requirements.txt on the Pi, or "
    "'sudo apt install python3-rpi.gpio'; on a Raspberry Pi 5 use "
    "'pip install rpi-lgpio' instead), check that the user is in the 'gpio' "
    "group, or run without hardware using --mock-gpio or 'gpio: {backend: mock}'."
)


def create_backend(
    force_mock: bool = False,
    strict: bool = True,
    backend: Optional[str] = None,
) -> GpioBackend:
    """Return the GPIO backend.

    ``force_mock=True`` or ``backend="mock"`` selects the in-memory mock.
    Otherwise the RPi.GPIO backend is loaded; if that fails and ``strict`` is
    true (the default) :class:`GpioBackendUnavailable` is raised. With
    ``strict=False`` the old behavior (warn and fall back to the mock) is kept.
    """
    if backend is not None and backend not in BACKEND_CHOICES:
        raise ValueError(
            f"gpio.backend must be one of {', '.join(BACKEND_CHOICES)}, got {backend!r}"
        )
    if force_mock or backend == "mock":
        log.info("Using mock GPIO backend (no hardware is switched)")
        return MockGpioBackend()
    try:
        return RPiGpioBackend()
    except (ImportError, RuntimeError) as exc:
        if strict:
            raise GpioBackendUnavailable(
                f"GPIO backend 'rpi' unavailable: {exc}. {_HINT}"
            ) from exc
        log.warning("RPi.GPIO unavailable (%s) — using mock GPIO backend", exc)
        return MockGpioBackend()
