"""GPIO pin configuration types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import logging

log = logging.getLogger(__name__)

SUPPORTED_DIRECTIONS = frozenset({"output", "input", "pwm_output"})
PWM_MODES = ("software", "hardware")


@dataclass
class PinConfig:
    pin: int
    alias: str
    direction: str
    initial: bool = False
    pull: Optional[str] = None
    invert: bool = False
    debounce_ms: int = 50
    ha_name: str = ""
    ha_icon: str = ""
    ha_device_class: str = ""
    # pwm_output only
    frequency_hz: float = 1000.0
    initial_duty: float = 0.0
    pwm_mode: str = "software"
    pwm_chip: int = 0
    pwm_channel: Optional[int] = None
    ha_min: float = 0.0
    ha_max: float = 100.0
    ha_step: float = 1.0
    ha_unit: str = "%"
    ha_mode: str = "slider"

    @property
    def is_pwm(self) -> bool:
        return self.direction == "pwm_output"


def parse_pins(cfg: Dict[str, Any]) -> List[PinConfig]:
    pins: List[PinConfig] = []
    for entry in cfg.get("pins", []):
        direction = entry.get("direction", "output")
        if direction not in SUPPORTED_DIRECTIONS:
            log.warning(
                "Skipping pin %s (%s): direction %r not supported yet",
                entry.get("alias"),
                entry.get("pin"),
                direction,
            )
            continue
        ha = entry.get("ha", {}) or {}
        pin = PinConfig(
            pin=int(entry["pin"]),
            alias=str(entry["alias"]),
            direction=direction,
            initial=bool(entry.get("initial", False)),
            pull=entry.get("pull"),
            invert=bool(entry.get("invert", False)),
            debounce_ms=int(entry.get("debounce_ms", 50)),
            ha_name=str(ha.get("name", entry["alias"])),
            ha_icon=str(ha.get("icon", "")),
            ha_device_class=str(ha.get("device_class", "")),
        )
        if direction == "pwm_output":
            _parse_pwm(pin, entry, ha)
        pins.append(pin)
    return pins

def _parse_pwm(pin: PinConfig, entry: Dict[str, Any], ha: Dict[str, Any]) -> None:
    where = f"pins[{pin.alias}]"
    pin.frequency_hz = float(entry.get("frequency_hz", 1000))
    if pin.frequency_hz <= 0:
        raise ValueError(f"{where}: frequency_hz must be > 0")
    pin.pwm_mode = str(entry.get("pwm_mode", "software"))
    if pin.pwm_mode not in PWM_MODES:
        raise ValueError(f"{where}: pwm_mode must be one of {', '.join(PWM_MODES)}")
    pin.pwm_chip = int(entry.get("pwm_chip", 0))
    pin.pwm_channel = int(entry["pwm_channel"]) if entry.get("pwm_channel") is not None else None
    pin.ha_min = float(ha.get("min", 0))
    pin.ha_max = float(ha.get("max", 100))
    pin.ha_step = float(ha.get("step", 1))
    if not 0 <= pin.ha_min < pin.ha_max <= 100:
        raise ValueError(f"{where}: ha.min/max must satisfy 0 <= min < max <= 100 (duty %)")
    pin.ha_unit = str(ha.get("unit_of_measurement", "%"))
    pin.ha_mode = str(ha.get("mode", "slider"))
    pin.initial_duty = float(entry.get("initial_duty", 0))
    if not pin.ha_min <= pin.initial_duty <= pin.ha_max and pin.initial_duty != 0:
        raise ValueError(f"{where}: initial_duty {pin.initial_duty:g} outside ha.min..max")
