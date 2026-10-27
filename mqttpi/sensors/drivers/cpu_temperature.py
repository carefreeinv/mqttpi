"""SoC temperature from the Linux thermal sysfs (every Raspberry Pi has it)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from mqttpi.sensors.model import Reading

DEFAULT_PATH = "/sys/class/thermal/thermal_zone0/temp"


class CpuTemperatureDriver:
    default_readings = {
        "temperature": {
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "state_class": "measurement",
            "precision": 1,
            "name": "CPU Temperature",
        }
    }

    def __init__(self, path: str = DEFAULT_PATH) -> None:
        self.path = Path(path)

    @classmethod
    def from_config(cls, spec: Dict[str, Any]) -> "CpuTemperatureDriver":
        return cls(str(spec.get("path", DEFAULT_PATH)))

    def read(self) -> Reading:
        raw = self.path.read_text(encoding="ascii").strip()  # millidegrees
        return Reading({"temperature": int(raw) / 1000.0})
