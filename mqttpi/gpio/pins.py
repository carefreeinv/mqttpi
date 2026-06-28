"""GPIO pin configuration types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import logging

log = logging.getLogger(__name__)

SUPPORTED_DIRECTIONS = frozenset({"output", "input"})


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
        ha = entry.get("ha", {})
        pins.append(
            PinConfig(
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
        )
    return pins