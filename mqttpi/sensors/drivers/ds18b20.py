"""DS18B20 1-Wire temperature probes via the Linux ``w1`` sysfs interface.

Enable the bus with ``dtoverlay=w1-gpio,gpiopin=4`` (Raspberry Pi) — no extra
Python dependency. Each probe appears as ``/sys/bus/w1/devices/28-xxxxxxxxxxxx``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from mqttpi.sensors.model import QUALITY_UNCERTAIN, Reading

DEFAULT_ROOT = "/sys/bus/w1/devices"
FAMILY_PREFIXES = ("28-", "10-", "22-", "3b-", "42-")  # DS18B20, DS18S20, DS1822, MAX31850, DS28EA00
#: The value a DS18B20 reports before its first conversion (or after a brown-out).
POWER_ON_RESET_MC = 85000

_T_RE = re.compile(r"t=(-?\d+)")


def list_probes(root: str = DEFAULT_ROOT) -> List[str]:
    base = Path(root)
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.name.lower().startswith(FAMILY_PREFIXES))


def parse_w1_slave(text: str) -> int:
    """Millidegrees from the two-line ``w1_slave`` file; raises on CRC failure."""
    lines = text.strip().splitlines()
    if len(lines) < 2 or not lines[0].strip().endswith("YES"):
        raise IOError("1-Wire CRC check failed")
    m = _T_RE.search(lines[1])
    if not m:
        raise IOError("1-Wire reply has no temperature")
    return int(m.group(1))


class Ds18b20Driver:
    default_readings = {
        "temperature": {
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "state_class": "measurement",
            "precision": 2,
        }
    }

    def __init__(self, address: Optional[str] = None, root: str = DEFAULT_ROOT) -> None:
        self.address = address.strip().lower() if address else None
        self.root = Path(root)

    @classmethod
    def from_config(cls, spec: Dict[str, Any]) -> "Ds18b20Driver":
        addr = spec.get("address", spec.get("rom"))
        return cls(str(addr) if addr else None, str(spec.get("sysfs_root", DEFAULT_ROOT)))

    def _device(self) -> Path:
        if self.address:
            return self.root / self.address
        probes = list_probes(str(self.root))
        if len(probes) != 1:
            raise IOError(
                f"DS18B20: set 'address' — found {len(probes)} probes under {self.root}"
                + (f" ({', '.join(probes)})" if probes else " (is dtoverlay=w1-gpio enabled?)")
            )
        return self.root / probes[0]

    def read(self) -> Reading:
        dev = self._device()
        temp_file = dev / "temperature"  # newer kernels: plain millidegrees
        if temp_file.exists():
            raw = temp_file.read_text(encoding="ascii").strip()
            if not raw:
                raise IOError(f"{dev.name}: empty read")
            millic = int(raw)
        else:
            millic = parse_w1_slave((dev / "w1_slave").read_text(encoding="ascii"))
        value = millic / 1000.0
        if millic == POWER_ON_RESET_MC:
            # Real 85.000 °C is possible but rare; a probe that lost power reports it.
            return Reading({"temperature": value}, quality=QUALITY_UNCERTAIN)
        if not -55.0 <= value <= 125.0:
            raise IOError(f"{dev.name}: {value} °C outside the sensor range")
        return Reading({"temperature": value})
