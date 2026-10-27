"""A narrow I2C bus interface for sensor drivers, plus the ``smbus2`` adapter.

Drivers depend on ``I2cBus`` only, so tests inject a fake register map.
``smbus2`` is an optional extra (``pip install 'mqttpi[i2c]'``).
"""

from __future__ import annotations

import threading
from typing import Callable, Dict, Protocol, Sequence, runtime_checkable


@runtime_checkable
class I2cBus(Protocol):
    def write(self, address: int, data: Sequence[int]) -> None: ...

    def read(self, address: int, length: int) -> bytes: ...

    def write_read(self, address: int, data: Sequence[int], length: int) -> bytes:
        """Write ``data`` (usually a register address), then read ``length`` bytes
        in the same transaction (repeated start)."""
        ...


class Smbus2Bus:
    """``I2cBus`` over ``/dev/i2c-<n>`` using ``smbus2``. Thread-safe."""

    def __init__(self, bus: int = 1) -> None:
        try:
            from smbus2 import SMBus, i2c_msg
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "I2C sensors need smbus2: pip install smbus2 (or 'mqttpi[i2c]'); "
                "enable I2C with raspi-config / dtparam=i2c_arm=on"
            ) from exc
        self._msg = i2c_msg
        self._bus = SMBus(bus)
        self._lock = threading.Lock()
        self.number = bus

    def write(self, address: int, data: Sequence[int]) -> None:
        with self._lock:
            self._bus.i2c_rdwr(self._msg.write(address, list(data)))

    def read(self, address: int, length: int) -> bytes:
        msg = self._msg.read(address, length)
        with self._lock:
            self._bus.i2c_rdwr(msg)
        return bytes(msg)

    def write_read(self, address: int, data: Sequence[int], length: int) -> bytes:
        w = self._msg.write(address, list(data))
        r = self._msg.read(address, length)
        with self._lock:
            self._bus.i2c_rdwr(w, r)
        return bytes(r)

    def close(self) -> None:
        self._bus.close()


BusFactory = Callable[[int], I2cBus]
_factory: BusFactory = Smbus2Bus
_buses: Dict[int, I2cBus] = {}
_buses_lock = threading.Lock()


def open_bus(number: int) -> I2cBus:
    """Shared bus instance per bus number (sensors on one bus share a lock)."""
    with _buses_lock:
        if number not in _buses:
            _buses[number] = _factory(number)
        return _buses[number]


def set_bus_factory(factory: BusFactory) -> None:
    """Swap the bus implementation (tests, or a custom adapter). Clears cached buses."""
    global _factory
    with _buses_lock:
        _factory = factory
        _buses.clear()


def reset_bus_factory() -> None:
    set_bus_factory(Smbus2Bus)


def parse_address(value, default: int) -> int:
    """Accept ``0x76``, ``"0x76"``, ``118`` or ``"118"``."""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    return int(str(value), 0)
