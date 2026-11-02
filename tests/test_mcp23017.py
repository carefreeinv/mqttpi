"""MCP23017 expander: register-level chip driver, routing backend, manager wiring."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from mqttpi.config import load_config
from mqttpi.gpio.backend import MockGpioBackend
from mqttpi.gpio.manager import GpioManager
from mqttpi.gpio.mcp23017 import (
    GPPU,
    IODIR,
    OLAT,
    ExpanderBackend,
    ExpanderPin,
    FakeMcp23017Bus,
    Mcp23017,
    build_expander_backend,
    expander_chips,
    parse_expander_pin,
)
from mqttpi.gpio.pins import parse_pins
from mqttpi.mqtt.factory import build_mqtt
from tests.test_gpio_manager import wait_until

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def chip(addr=0x20, **kw):
    bus = FakeMcp23017Bus([addr])
    clock = Clock()
    return bus, Mcp23017(bus, addr, clock=clock, **kw), clock


# -- chip driver ----------------------------------------------------------------

def test_output_setup_sets_latch_before_direction() -> None:
    bus, c, _ = chip()
    c.setup_output(0, True)
    c.setup_output(9, False)
    assert bus.reg16(0x20, IODIR) == 0xFFFF & ~0x0201
    assert bus.reg16(0x20, OLAT) == 0x0001
    assert bus.pin_level(0x20, 0) and not bus.pin_level(0x20, 9)
    c.write(9, True)
    c.write(0, False)
    assert bus.reg16(0x20, OLAT) == 0x0200
    assert c.olat == 0x0200


def test_inputs_pullups_and_read_cache() -> None:
    bus, c, clock = chip(read_cache_s=0.01)
    c.setup_input(3, "up")
    c.setup_input(12, None)
    assert bus.reg16(0x20, GPPU) == 0x0008
    assert c.read(3) is True and c.read(12) is False  # pull-up idle high / floating low
    bus.set_input(0x20, 3, False)
    bus.set_input(0x20, 12, True)
    n = bus.transactions
    assert c.read(3) is True  # cached within read_cache_s: no bus traffic
    assert bus.transactions == n
    clock.t += 0.02
    assert c.read(3) is False and c.read(12) is True
    assert bus.transactions == n + 1  # one 16-bit GPIO read serves every pin


def test_pull_down_rejected() -> None:
    _, c, _ = chip()
    with pytest.raises(ValueError, match="only pull 'up'"):
        c.setup_input(0, "down")


def test_reset_detected_and_state_reapplied() -> None:
    bus, c, clock = chip(verify_interval_s=5.0)
    c.setup_output(0, True)
    c.setup_input(1, "up")
    bus.reset(0x20)  # brown-out: every pin an input, latches low
    assert not bus.pin_level(0x20, 0)
    clock.t += 6
    assert c.check()
    assert bus.pin_level(0x20, 0) and bus.reg16(0x20, GPPU) == 0x0002
    assert c.reinit_count >= 2


def test_i2c_error_keeps_latch_and_recovers() -> None:
    bus, c, clock = chip()
    c.setup_output(0, False)
    bus.fail = True
    with pytest.raises(OSError):
        c.write(0, True)
    assert c.olat == 0  # failed write not committed
    assert not c.check()
    bus.reset(0x20)  # chip power-cycled while unreachable
    bus.fail = False
    assert c.check()  # dirty → full re-apply
    assert bus.reg16(0x20, IODIR) & 1 == 0 and not bus.pin_level(0x20, 0)
    c.write(0, True)
    assert bus.pin_level(0x20, 0)


def test_absent_chip_at_setup_does_not_raise(caplog) -> None:
    bus = FakeMcp23017Bus()
    c = Mcp23017(bus, 0x21, clock=Clock())
    c.setup_output(0, True)  # logged, configured later
    assert "unreachable" in caplog.text
    bus.add_chip(0x21)
    assert c.check() and bus.pin_level(0x21, 0)


def test_release_restores_power_on_state() -> None:
    bus, c, _ = chip()
    c.setup_output(5, True)
    c.release()
    assert bus.reg16(0x20, IODIR) == 0xFFFF and bus.reg16(0x20, OLAT) == 0


def test_bad_address() -> None:
    with pytest.raises(ValueError, match="0x20-0x27"):
        Mcp23017(FakeMcp23017Bus(), 0x40)


# -- config ---------------------------------------------------------------------

def test_parse_expander_pin_forms() -> None:
    assert [parse_expander_pin(v, "x") for v in (0, "15", "A0", "B7", "gpb3")] == [0, 15, 0, 15, 11]
    for bad in (16, -1, "C1", "A8"):
        with pytest.raises(ValueError):
            parse_expander_pin(bad, "x")


def test_parse_pins_expander_entries() -> None:
    pins = parse_pins({"pins": [
        {"alias": "r1", "direction": "output", "default": True,
         "homeassistant": {"name": "Relay 1"}, "expander": {"chip": 0x20, "pin": 0}},
        {"alias": "s1", "direction": "input", "pull": "up", "expander": {"chip": "0x21", "pin": "B0"}},
        {"alias": "n1", "bcm": 17},
    ]})
    assert [p.pin for p in pins] == [ExpanderPin(0x20, 0), ExpanderPin(0x21, 8), 17]
    assert pins[0].initial is True and pins[0].ha_name == "Relay 1"
    assert str(pins[1].pin) == "0x21:GPB0"
    with pytest.raises(ValueError, match="already used"):
        parse_pins({"pins": [{"alias": "a", "expander": {"chip": 0x20, "pin": 1}},
                             {"alias": "b", "expander": {"chip": 0x20, "pin": "A1"}}]})
    with pytest.raises(ValueError, match="not both"):
        parse_pins({"pins": [{"alias": "a", "pin": 4, "expander": {"chip": 0x20, "pin": 1}}]})
    with pytest.raises(ValueError, match="pwm_output"):
        parse_pins({"pins": [{"alias": "a", "direction": "pwm_output", "expander": {"chip": 0x20, "pin": 1}}]})


def test_expander_chips_section() -> None:
    assert expander_chips({}) == {}
    assert expander_chips({"expanders": {"mcp23017": {"enabled": False, "chips": [{"address": 0x20}]}}}) == {}
    section = {"bus": 3, "chips": [{"address": "0x20"}, {"address": 0x21, "bus": 1}]}
    chips = expander_chips({"expanders": {"mcp23017": section}})
    assert {a: c["bus"] for a, c in chips.items()} == {0x20: 3, 0x21: 1}
    with pytest.raises(ValueError, match="twice"):
        expander_chips({"expanders": {"mcp23017": {"chips": [{"address": 0x20}, {"address": 0x20}]}}})


def test_routing_backend() -> None:
    native = MockGpioBackend()
    bus = FakeMcp23017Bus([0x20])
    be = ExpanderBackend(native, {0x20: Mcp23017(bus, 0x20)}, watchdog_s=0)
    be.setup_output(17, True)
    be.setup_output(ExpanderPin(0x20, 4), True)
    assert native.read(17) and bus.pin_level(0x20, 4)
    with pytest.raises(ValueError, match="no MCP23017"):
        be.setup_output(ExpanderPin(0x22, 0), True)
    with pytest.raises(ValueError, match="PWM"):
        be.open_pwm(ExpanderPin(0x20, 1), 1000)
    be.cleanup()
    assert bus.reg16(0x20, IODIR) == 0xFFFF


def test_build_backend_reset_pin_and_passthrough() -> None:
    native = MockGpioBackend()
    assert build_expander_backend({}, native, mock=True) is native
    be = build_expander_backend({"expanders": {"mcp23017": {"chips": [{"address": 0x20, "reset_pin": 5}]}}},
                                native, mock=True, watchdog_s=0)
    assert isinstance(be, ExpanderBackend) and native.read(5) is True  # RESET held released


# -- manager ----------------------------------------------------------------------

def start_manager(fake_paho, cfg):
    cfg = dict(cfg)
    cfg["mqtt"] = {"host": "b", "base_topic": "mqttpi/x"}
    cfg.setdefault("device", {"id": "x"})
    conn = build_mqtt(cfg)
    mgr = GpioManager(cfg, conn, mock_gpio=True)
    conn.set_message_handler(mgr.handle_mqtt_message)
    conn.connect()
    fake_paho.last.simulate_connect()
    mgr.start()
    return mgr, fake_paho.last


def test_relay_bank_32_example_runs_with_fake_expanders(fake_paho) -> None:
    cfg = load_config(ROOT / "examples" / "relay-bank-32.yaml")
    mgr, client = start_manager(fake_paho, cfg)
    try:
        assert mgr.backend_name == "mock+mcp23017"
        assert len(mgr.states()) == 32
        chips = mgr.backend.chips
        bus = chips[0x21].bus
        client.simulate_message("mqttpi/x/gpio/relay_20/set", "ON")
        assert wait_until(lambda: bus.pin_level(0x21, 3))
        assert client.last_payload("mqttpi/x/gpio/relay_20/state") == "ON"
        assert ("mqttpi/x/gpio/relay_32/set", 1) in client.subscriptions
    finally:
        mgr.stop()
    assert bus.reg16(0x21, IODIR) == 0xFFFF  # released on shutdown


def test_relay_bank_16_example_still_runs(fake_paho) -> None:
    cfg = load_config(ROOT / "examples" / "relay-bank-16.yaml")
    mgr, _ = start_manager(fake_paho, cfg)
    try:
        assert mgr.backend_name == "mock"  # native pins only
    finally:
        mgr.stop()


def expander_cfg():
    return {"device": {"id": "x", "board": "pi4"},
            "expanders": {"mcp23017": {"check_interval_s": 0, "chips": [{"address": 0x20}]}},
            "pins": [
                {"alias": "relay", "direction": "output", "invert": True, "expander": {"chip": 0x20, "pin": 0}},
                {"alias": "door", "direction": "input", "pull": "up", "invert": True, "debounce_ms": 0,
                 "expander": {"chip": 0x20, "pin": "B0"}},
                {"alias": "native", "pin": 17},
            ]}


def test_manager_inputs_outputs_invert_and_bus_errors(fake_paho, caplog) -> None:
    mgr, client = start_manager(fake_paho, expander_cfg())
    bus = mgr.backend.chips[0x20].bus
    try:
        assert bus.pin_level(0x20, 0) is True  # active-low relay off = HIGH
        mgr.request_output("relay", True)
        assert bus.pin_level(0x20, 0) is False
        bus.set_input(0x20, 8, False)  # switch closes to GND
        assert wait_until(lambda: client.last_payload("mqttpi/x/gpio/door/state") == "ON")
        # bus failure: command reports the old state, poll loop keeps running
        bus.fail = True
        with caplog.at_level(logging.WARNING):
            assert mgr.request_output("relay", False) is True
            assert wait_until(lambda: "read failed" in caplog.text)
        bus.fail = False
        bus.set_input(0x20, 8, None)
        assert wait_until(lambda: client.last_payload("mqttpi/x/gpio/door/state") == "OFF")
        assert mgr.request_output("relay", False) is False
        assert bus.pin_level(0x20, 0) is True
    finally:
        mgr.stop()


def test_expander_outputs_go_through_command_filters(fake_paho) -> None:
    from mqttpi.gpio.commands import mutually_exclusive

    cfg = expander_cfg()
    cfg["pins"].append({"alias": "relay2", "direction": "output", "expander": {"chip": 0x20, "pin": 1}})
    mgr, _ = start_manager(fake_paho, cfg)
    try:
        mgr.add_command_filter(mutually_exclusive("relay", "relay2"))
        assert mgr.request_output("relay", True) is True
        assert mgr.request_output("relay2", True) is False  # rejected
    finally:
        mgr.stop()
