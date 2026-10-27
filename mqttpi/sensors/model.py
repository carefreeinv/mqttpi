"""Core sensor types: ``Reading``, ``SensorDriver`` and per-entity specs."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, runtime_checkable

QUALITY_GOOD = "good"
#: Value published, but flagged (e.g. outside the sensor's rated range).
QUALITY_UNCERTAIN = "uncertain"
#: Read failed; nothing is published.
QUALITY_BAD = "bad"
QUALITIES = (QUALITY_GOOD, QUALITY_UNCERTAIN, QUALITY_BAD)


@dataclass(frozen=True)
class Reading:
    """One read of a driver: values keyed by reading name (``temperature``…)."""

    values: Mapping[str, Optional[float]]
    timestamp: float = field(default_factory=time.time)  # wall clock, seconds
    quality: str = QUALITY_GOOD

    def __post_init__(self) -> None:
        if self.quality not in QUALITIES:
            raise ValueError(f"Reading.quality must be one of {QUALITIES}, got {self.quality!r}")

    def numeric(self) -> Dict[str, float]:
        """Values that are real finite numbers (``None``/NaN/inf dropped)."""
        out: Dict[str, float] = {}
        for key, value in self.values.items():
            if isinstance(value, bool) or value is None:
                continue
            try:
                f = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(f):
                out[key] = f
        return out


@runtime_checkable
class SensorDriver(Protocol):
    """A sensor driver. ``read()`` may block (bus I/O); the scheduler runs it
    in a worker thread and enforces ``timeout_s``. Raise or return a ``bad``
    reading on failure.

    Optional attributes: ``default_readings`` (``{key: {unit_of_measurement,
    device_class, state_class, icon, precision}}``) used when the config lists
    no ``readings``, and ``close()``.
    """

    def read(self) -> Reading: ...


@dataclass(frozen=True)
class EntitySpec:
    """One Home Assistant ``sensor`` entity fed by one key of a driver's readings."""

    sensor: str  # config name of the sensor (``cpu``)
    key: str  # reading key (``temperature``)
    alias: str  # MQTT/HA object id (``cpu_temperature``)
    name: str
    unit: Optional[str] = None
    device_class: Optional[str] = None
    state_class: Optional[str] = "measurement"
    icon: Optional[str] = None
    precision: Optional[int] = None
    retain: bool = True
    extra: Mapping[str, Any] = field(default_factory=dict)

    def format(self, value: float) -> str:
        if self.precision is not None:
            return f"{round(value, self.precision):.{self.precision}f}"
        return repr(value) if not float(value).is_integer() else str(int(value))
