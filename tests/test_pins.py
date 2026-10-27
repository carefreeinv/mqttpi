"""Pin parsing."""

from __future__ import annotations

import logging

import pytest

from mqttpi.gpio.pins import PinConfig, parse_pins


def test_defaults() -> None:
    (pin,) = parse_pins({"pins": [{"pin": "17", "alias": "relay"}]})
    assert pin == PinConfig(pin=17, alias="relay", direction="output", initial=False,
                            pull=None, invert=False, debounce_ms=50, ha_name="relay")


def test_all_fields() -> None:
    (pin,) = parse_pins({"pins": [{
        "pin": 27, "alias": "door", "direction": "input", "pull": "up", "invert": True,
        "debounce_ms": 120, "initial": True,
        "ha": {"name": "Front door", "icon": "mdi:door", "device_class": "door"},
    }]})
    assert (pin.pin, pin.direction, pin.pull, pin.invert, pin.debounce_ms, pin.initial) == (
        27, "input", "up", True, 120, True)
    assert (pin.ha_name, pin.ha_icon, pin.ha_device_class) == ("Front door", "mdi:door", "door")


def test_unsupported_directions_are_skipped_with_warning(caplog) -> None:
    caplog.set_level(logging.WARNING)
    pins = parse_pins({"pins": [
        {"pin": 18, "alias": "fan", "direction": "pwm"},
        {"pin": 26, "alias": "adc", "direction": "analog"},
        {"pin": 17, "alias": "relay"},
    ]})
    assert [p.alias for p in pins] == ["relay"]
    assert "fan" in caplog.text and "not supported yet" in caplog.text


def test_no_pins_key() -> None:
    assert parse_pins({}) == []


def test_missing_required_key_raises() -> None:
    with pytest.raises(KeyError):
        parse_pins({"pins": [{"alias": "x"}]})
    with pytest.raises(KeyError):
        parse_pins({"pins": [{"pin": 4}]})
