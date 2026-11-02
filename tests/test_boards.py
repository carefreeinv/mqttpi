from __future__ import annotations

import logging
from pathlib import Path

import pytest

from mqttpi.boards import BOARDS, get_board, validate_pins
from mqttpi.config import load_config
from mqttpi.gpio.manager import GpioManager
from mqttpi.mqtt.factory import build_mqtt

ROOT = Path(__file__).resolve().parents[1]


def cfg(board, pins, **extra):
    return {"device": {"id": "n", "board": board}, "mqtt": {"host": "b"}, "pins": pins, **extra}


@pytest.mark.parametrize("name", ["pizero", "pizero2w", "PiZero_W", "zero2w", "pi-zero-2-w"])
def test_pizero_aliases(name) -> None:
    assert get_board(name) is BOARDS["pizero"]


def test_pizero_profile() -> None:
    b = BOARDS["pizero"]
    assert b.gpio == frozenset(range(28))
    assert b.hardware_pwm == {12, 13, 18, 19}
    assert not b.adc
    assert any("2.4 GHz" in n for n in b.notes)


def test_unknown_or_missing_board_is_not_validated(caplog) -> None:
    assert validate_pins({"pins": [{"pin": 99, "alias": "x"}]}) == []
    caplog.set_level(logging.WARNING)
    assert validate_pins(cfg("toaster", [{"pin": 99, "alias": "x"}])) == []
    assert "Unknown device.board" in caplog.text


def test_invalid_pin_rejected_for_board() -> None:
    with pytest.raises(ValueError, match="no GPIO30"):
        validate_pins(cfg("pizero", [{"pin": 30, "alias": "x"}]))
    with pytest.raises(ValueError, match="no GPIO24"):
        validate_pins(cfg("picow", [{"pin": 24, "alias": "x"}]))


def test_duplicate_pin_rejected() -> None:
    with pytest.raises(ValueError, match="already used by a"):
        validate_pins(cfg("pizero", [{"pin": 17, "alias": "a"}, {"pin": 17, "alias": "b"}]))


def test_enabled_bus_conflict_rejected_disabled_bus_ignored() -> None:
    pins = [{"pin": 2, "alias": "x"}]
    with pytest.raises(ValueError, match="buses.i2c.sda"):
        validate_pins(cfg("pizero", pins, buses={"i2c": {"enabled": True, "controller": 1, "sda": 2, "scl": 3}}))
    validate_pins(cfg("pizero", pins, buses={"i2c": {"enabled": False, "sda": 2, "scl": 3}}))


def test_bms_serial0_claims_uart_pins() -> None:
    pins = [{"pin": 14, "alias": "x"}]
    with pytest.raises(ValueError, match="UART"):
        validate_pins(cfg("pizero", pins, bms={"enabled": True, "port": "/dev/serial0"}))
    validate_pins(cfg("pizero", pins, bms={"enabled": True, "port": "/dev/ttyUSB0"}))


def test_soft_warnings() -> None:
    w = validate_pins(cfg("pizero", [
        {"pin": 0, "alias": "id"},
        {"pin": 5, "alias": "adc", "direction": "analog"},
        {"pin": 6, "alias": "fan", "direction": "pwm"},
        {"pin": 18, "alias": "fan2", "direction": "pwm"},
    ]))
    assert len(w) == 3
    assert "EEPROM" in w[0] and "no ADC" in w[1] and "hardware PWM" in w[2]


def test_hardware_pwm_mode_needs_hardware_pin() -> None:
    with pytest.raises(ValueError, match="not a hardware PWM pin"):
        validate_pins(cfg("pizero", [{"pin": 6, "alias": "m", "direction": "pwm_output", "pwm_mode": "hardware"}]))
    assert validate_pins(cfg("pizero", [{"pin": 6, "alias": "m", "direction": "pwm_output"}])) == []
    validate_pins(cfg("pizero", [{"pin": 18, "alias": "m", "direction": "pwm_output", "pwm_mode": "hardware"}]))


def test_all_errors_reported_together() -> None:
    with pytest.raises(ValueError) as exc:
        validate_pins(cfg("pi4", [{"pin": 40, "alias": "a"}, {"pin": "x", "alias": "b"}]))
    assert "GPIO40" in str(exc.value) and "'x'" in str(exc.value)


def test_gpio_manager_validates_on_startup(fake_paho) -> None:
    c = cfg("pizero", [{"pin": 31, "alias": "x", "direction": "output"}])
    with pytest.raises(ValueError, match="no GPIO31"):
        GpioManager(c, build_mqtt(c), mock_gpio=True)


def test_pizero_example_loads(fake_paho) -> None:
    c = load_config(ROOT / "examples" / "pizero-relays.yaml")
    assert get_board(c["device"]["board"]) is BOARDS["pizero"]
    mgr = GpioManager(c, build_mqtt(c), mock_gpio=True)
    assert [p.alias for p in mgr.pins] == ["relay_1", "relay_2", "relay_3", "relay_4",
                                           "contact_1", "contact_2"]


def test_every_example_passes_board_validation() -> None:
    for path in sorted((ROOT / "examples").rglob("*.yaml")) + [ROOT / "config.example.yaml"]:
        validate_pins(load_config(path))  # raises on hard errors
