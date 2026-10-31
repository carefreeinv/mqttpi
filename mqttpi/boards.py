"""Board profiles: which GPIO numbers exist, hardware PWM, ADC, known limits.

Profiles are data only. ``device.board`` selects one; an unknown or missing
board skips validation (backward compatible). All Raspberry Pi 40-pin models
share BCM numbering 0-27.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BoardProfile:
    key: str
    name: str
    gpio: FrozenSet[int]
    hardware_pwm: FrozenSet[int] = frozenset()
    adc: FrozenSet[int] = frozenset()
    #: Pins with a default function worth a warning when used as plain GPIO.
    reserved: Mapping[int, str] = field(default_factory=dict)
    #: GPIO used by the primary UART (``/dev/serial0``) when a BMS is enabled.
    serial0: Tuple[int, ...] = ()
    notes: Tuple[str, ...] = ()


_PI_GPIO = frozenset(range(0, 28))
_PI_RESERVED = {
    0: "ID EEPROM (ID_SD) — keep free for HAT detection",
    1: "ID EEPROM (ID_SC) — keep free for HAT detection",
}
_PI_PWM = frozenset({12, 13, 18, 19})

_PI = dict(gpio=_PI_GPIO, hardware_pwm=_PI_PWM, reserved=_PI_RESERVED, serial0=(14, 15))

BOARDS: Dict[str, BoardProfile] = {
    "pi3": BoardProfile("pi3", "Raspberry Pi 3", **_PI),
    "pi4": BoardProfile("pi4", "Raspberry Pi 4", **_PI),
    "pi5": BoardProfile(
        "pi5", "Raspberry Pi 5", **_PI,
        notes=("RPi.GPIO does not support the Pi 5; install rpi-lgpio (drop-in replacement).",),
    ),
    "pizero": BoardProfile(
        "pizero", "Raspberry Pi Zero W / Zero 2 W", **_PI,
        notes=(
            "Zero W: single-core ARMv6 — keep poll intervals relaxed; Zero 2 W is quad-core.",
            "Wi-Fi is 2.4 GHz only.",
            "No ADC: analog inputs need an external converter (e.g. ADS1115 on I2C).",
        ),
    ),
    "picow": BoardProfile(
        "picow", "Raspberry Pi Pico W",
        gpio=frozenset(range(0, 23)) | frozenset({26, 27, 28}),
        hardware_pwm=frozenset(range(0, 23)) | frozenset({26, 27, 28}),
        adc=frozenset({26, 27, 28}),
        notes=("Runs the Linux daemon for bring-up only; GP23-25 and GP29 are used by the board.",),
    ),
}

#: Accepted spellings for ``device.board``.
ALIASES = {
    "pi3b": "pi3", "pi3b+": "pi3", "pi4b": "pi4", "pi400": "pi4", "pi5b": "pi5",
    "pizero_w": "pizero", "pizerow": "pizero", "pizero2": "pizero", "pizero2w": "pizero",
    "pizero_2_w": "pizero", "zero": "pizero", "zero2w": "pizero",
    "pico_w": "picow", "pico": "picow",
}


def get_board(name: Optional[str]) -> Optional[BoardProfile]:
    if not name:
        return None
    key = _norm(name)
    for alias, target in ALIASES.items():
        if _norm(alias) == key:
            key = target
    return BOARDS.get(key)


def _norm(name: str) -> str:
    return "".join(ch for ch in str(name).strip().lower() if ch not in "-_ ")


def _bus_pins(cfg: Dict[str, Any], board: BoardProfile) -> Dict[int, str]:
    """GPIO claimed by enabled buses (any integer setting except ``controller``)."""
    used: Dict[int, str] = {}
    buses = cfg.get("buses") or {}
    if isinstance(buses, dict):
        for bus, settings in buses.items():
            if not isinstance(settings, dict) or not settings.get("enabled"):
                continue
            for key, value in settings.items():
                if key in ("controller", "enabled", "frequency", "baudrate"):
                    continue
                values = value if isinstance(value, list) else [value]
                for v in values:
                    if isinstance(v, int) and not isinstance(v, bool):
                        used[v] = f"buses.{bus}.{key}"
    bms = cfg.get("bms") or {}
    if isinstance(bms, dict) and bms.get("enabled") and board.serial0:
        port = str(bms.get("port", "/dev/serial0"))
        if port in ("/dev/serial0", "/dev/ttyAMA0", "/dev/ttyS0"):
            for p in board.serial0:
                used[p] = f"bms.port {port} (UART TX/RX)"
    return used


def validate_pins(cfg: Dict[str, Any]) -> List[str]:
    """Check ``pins[]`` against ``device.board``.

    Raises ``ValueError`` listing every hard error (pin missing on the board,
    pin used twice, pin claimed by an enabled bus). Returns warnings (soft
    issues) after logging them. Unknown/missing boards are not validated.
    """
    board_name = (cfg.get("device") or {}).get("board")
    board = get_board(board_name)
    if board is None:
        if board_name:
            log.warning("Unknown device.board %r — pin validation skipped (known: %s)",
                        board_name, ", ".join(sorted(BOARDS)))
        return []

    errors: List[str] = []
    warnings: List[str] = []
    seen: Dict[int, str] = {}
    bus_pins = _bus_pins(cfg, board)

    for entry in cfg.get("pins") or []:
        if not isinstance(entry, dict) or "pin" not in entry:
            continue
        try:
            pin = int(entry["pin"])
        except (TypeError, ValueError):
            errors.append(f"pin {entry.get('pin')!r} ({entry.get('alias')}): not a GPIO number")
            continue
        alias = entry.get("alias", "?")
        direction = entry.get("direction", "output")
        label = f"GPIO{pin} ({alias})"
        if pin not in board.gpio:
            errors.append(f"{label}: {board.name} has no GPIO{pin} "
                          f"(valid: {_ranges(board.gpio)})")
            continue
        if pin in seen:
            errors.append(f"{label}: already used by {seen[pin]}")
        seen[pin] = str(alias)
        if pin in bus_pins:
            errors.append(f"{label}: claimed by enabled {bus_pins[pin]}")
        if pin in board.reserved:
            warnings.append(f"{label}: {board.reserved[pin]}")
        if direction == "analog" and pin not in board.adc:
            warnings.append(f"{label}: {board.name} has no ADC on this pin"
                            + ("" if board.adc else " (no ADC at all; use an external converter)"))
        if direction == "pwm" and pin not in board.hardware_pwm:
            warnings.append(f"{label}: not a hardware PWM pin on {board.name} "
                            f"(hardware PWM: {_ranges(board.hardware_pwm)})")

    for w in warnings:
        log.warning("Board %s: %s", board.key, w)
    if errors:
        raise ValueError(f"Invalid pins for device.board {board_name!r}:\n  - " + "\n  - ".join(errors))
    return warnings


def _ranges(pins: FrozenSet[int]) -> str:
    out: List[str] = []
    for p in sorted(pins):
        if out and isinstance(out[-1], list) and out[-1][1] == p - 1:
            out[-1][1] = p
        else:
            out.append([p, p])  # type: ignore[arg-type]
    return ", ".join(f"{a}" if a == b else f"{a}-{b}" for a, b in out)  # type: ignore[misc]
