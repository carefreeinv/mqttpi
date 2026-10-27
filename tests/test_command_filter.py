from __future__ import annotations

import logging
import time

import pytest

from mqttpi.daemon import Daemon
from mqttpi.gpio.commands import (
    CommandDecision,
    CommandRequest,
    block_while,
    mutually_exclusive,
    run_filters,
)
from mqttpi.gpio.manager import GpioManager
from mqttpi.mqtt.client import MqttConnection

BASE = "mqttpi/unit"
CFG = {
    "device": {"id": "unit"},
    "mqtt": {"homeassistant": {"discovery": False}},
    "pins": [
        {"alias": "extend", "pin": 17, "direction": "output"},
        {"alias": "retract", "pin": 27, "direction": "output"},
        {"alias": "limit_out", "pin": 22, "direction": "input"},
        {"alias": "active_low", "pin": 5, "direction": "output", "invert": True},
    ],
}


@pytest.fixture
def mgr(fake_paho):
    conn = MqttConnection("broker", base_topic=BASE)
    conn.connect()
    m = GpioManager(CFG, conn, mock_gpio=True)
    m.client = fake_paho.last
    return m


def send(m, alias, payload):
    m.handle_mqtt_message(f"{BASE}/gpio/{alias}/set", payload)


def hw(m, alias):
    pin = {"extend": 17, "retract": 27, "limit_out": 22, "active_low": 5}[alias]
    return m.backend.read(pin)


def test_no_filter_behaves_as_before(mgr) -> None:
    send(mgr, "extend", "ON")
    assert hw(mgr, "extend") is True
    assert mgr.client.last_payload(f"{BASE}/gpio/extend/state") == "ON"


def test_filter_sees_request_and_accepts(mgr) -> None:
    seen = []
    mgr.add_command_filter(lambda req: seen.append(req))
    send(mgr, "extend", "ON")
    req = seen[0]
    assert isinstance(req, CommandRequest)
    assert (req.alias, req.value, req.current, req.payload) == ("extend", True, False, "ON")
    assert req.source == f"{BASE}/gpio/extend/set"
    assert req.states.get("retract", False) is False
    with pytest.raises(TypeError):
        req.states["x"] = True  # read-only snapshot
    assert hw(mgr, "extend") is True


def test_reject_keeps_hardware_and_republishes_true_state(mgr, caplog) -> None:
    mgr.add_command_filter(lambda req: CommandDecision.reject("maintenance lockout"))
    mgr.client.published.clear()
    with caplog.at_level(logging.INFO):
        send(mgr, "extend", "ON")
    assert hw(mgr, "extend") is False
    assert mgr.client.last_payload(f"{BASE}/gpio/extend/state") == "OFF"
    assert "maintenance lockout" in caplog.text


def test_modify_changes_value(mgr) -> None:
    mgr.add_command_filter(lambda req: CommandDecision.modify(False, "forced off"))
    send(mgr, "extend", "ON")
    assert hw(mgr, "extend") is False
    assert mgr.client.last_payload(f"{BASE}/gpio/extend/state") == "OFF"


def test_filter_exception_is_reject(mgr, caplog) -> None:
    def broken(req):
        raise RuntimeError("bug")

    mgr.add_command_filter(broken)
    with caplog.at_level(logging.ERROR):
        send(mgr, "extend", "ON")
    assert hw(mgr, "extend") is False
    assert "raised" in caplog.text


def test_first_reject_wins_and_modifies_chain() -> None:
    calls = []

    def f1(req):
        calls.append(("f1", req.value))
        return CommandDecision.modify(5, "clamp")

    def f2(req):
        calls.append(("f2", req.value))
        return CommandDecision.reject("nope")

    def f3(req):  # pragma: no cover - must not run
        calls.append(("f3", req.value))

    req = CommandRequest(alias="a", value=9, current=0, source="api")
    out = run_filters([f1, f2, f3], req)
    assert not out.accepted and out.value == 0
    assert calls == [("f1", 9), ("f2", 5)]
    assert out.reasons == ("clamp", "nope")


def test_slow_filter_warns(caplog) -> None:
    def slow(req):
        time.sleep(0.08)

    with caplog.at_level(logging.WARNING):
        run_filters([slow], CommandRequest("a", True, False, "api"))
    assert "non-blocking" in caplog.text


def test_mutually_exclusive_interlock(mgr) -> None:
    mgr.add_command_filter(mutually_exclusive("extend", "retract"))
    send(mgr, "extend", "ON")
    send(mgr, "retract", "ON")  # rejected: extend is ON
    assert hw(mgr, "extend") is True and hw(mgr, "retract") is False
    assert mgr.client.last_payload(f"{BASE}/gpio/retract/state") == "OFF"
    send(mgr, "extend", "OFF")
    send(mgr, "retract", "ON")
    assert hw(mgr, "extend") is False and hw(mgr, "retract") is True


def test_mutually_exclusive_needs_two() -> None:
    with pytest.raises(ValueError):
        mutually_exclusive("only")


def test_block_while_input_active(mgr) -> None:
    mgr.add_command_filter(block_while("extend", "limit_out"))
    mgr._input_state["limit_out"] = True
    send(mgr, "extend", "ON")
    assert hw(mgr, "extend") is False
    mgr._input_state["limit_out"] = False
    send(mgr, "extend", "ON")
    assert hw(mgr, "extend") is True
    mgr._input_state["limit_out"] = True
    send(mgr, "extend", "OFF")  # turning off is always allowed
    assert hw(mgr, "extend") is False


def test_request_output_goes_through_filters(mgr) -> None:
    mgr.add_command_filter(mutually_exclusive("extend", "retract"))
    assert mgr.request_output("extend", True) is True
    assert mgr.request_output("retract", True) is False
    with pytest.raises(KeyError):
        mgr.request_output("nope", True)


def test_invert_output_is_active_low(mgr) -> None:
    mgr.start()
    assert hw(mgr, "active_low") is True  # initial OFF → pin HIGH
    send(mgr, "active_low", "ON")
    assert hw(mgr, "active_low") is False
    assert mgr.client.last_payload(f"{BASE}/gpio/active_low/state") == "ON"
    mgr.stop()


def test_daemon_registers_filters(fake_paho, monkeypatch) -> None:
    f = mutually_exclusive("extend", "retract")
    d = Daemon(CFG, mock_gpio=True, command_filters=[f])
    monkeypatch.setattr(d._stop, "wait", lambda timeout=None: True)
    d.run()
    assert d.gpio is not None and d.gpio.command_filters == [f]
