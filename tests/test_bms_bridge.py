"""BMS bridge and subsystem with a fake serial port and the fake MQTT client."""

from __future__ import annotations

import time

import pytest
import yaml

from mqttpi.bms import bridge, jbd_uart
from mqttpi.bms.jbd_protocol import CMD_CELLINFO, CMD_HWINFO
from mqttpi.bms.subsystem import BmsSubsystem, bms_enabled
from mqttpi.mqtt.client import MqttConnection
from tests.jbd_frames import CELLINFO_FRAME, HWINFO_FRAME
from tests.test_jbd_protocol import FakeSerial

CFG = {
    "device": {"id": "node1"},
    "mqtt": {"host": "b", "base_topic": "mqttpi/node1"},
    "bms": {"enabled": True, "port": "/dev/fake", "poll_interval": 0.2, "retry_delay": 0.2,
            "response_timeout": 0.3, "ha": {"device_id": "pack1"}},
}


@pytest.fixture
def bms_serial(monkeypatch):
    """Patch serial.Serial: a working BMS by default; set .silent to make it mute."""
    state = {"silent": False, "opened": 0}

    def factory(**_kw):
        state["opened"] += 1
        replies = {} if state["silent"] else {CMD_HWINFO: HWINFO_FRAME, CMD_CELLINFO: CELLINFO_FRAME}
        return FakeSerial(replies)

    monkeypatch.setattr(jbd_uart.serial, "Serial", factory)
    return state


def wait_until(pred, timeout=3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.01)
    return pred()


def test_poll_once_publishes_state_discovery_and_online(fake_paho, bms_serial) -> None:
    pub = bridge.build_publisher(CFG)
    assert bridge.poll_once(CFG, pub) is True
    c = fake_paho.last
    assert c.last_payload("mqttpi/node1/bms/soc/state") == "80"
    assert c.last_payload("mqttpi/node1/status") == "online"
    assert c.published_to("homeassistant/sensor/pack1_soc/config")
    # discovery only once per connection
    bridge.poll_once(CFG, pub)
    assert len(c.published_to("homeassistant/sensor/pack1_soc/config")) == 1


def test_poll_once_requires_port(fake_paho) -> None:
    pub = bridge.build_publisher(CFG)
    with pytest.raises(ValueError, match="bms.port"):
        bridge.poll_once({**CFG, "bms": {"port": " "}}, pub)


def test_poll_once_timeout_closes_port(fake_paho, bms_serial) -> None:
    bms_serial["silent"] = True
    with pytest.raises(TimeoutError):
        bridge.poll_once(CFG, bridge.build_publisher(CFG))


def test_main_once(tmp_path, fake_paho, bms_serial, monkeypatch) -> None:
    monkeypatch.setattr(MqttConnection, "wait_connected", lambda self, timeout=None: True)
    cfg = tmp_path / "c.yaml"
    cfg.write_text(yaml.safe_dump(CFG))
    assert bridge.main(["-c", str(cfg), "-s", str(tmp_path / "none.yaml"), "--once"]) == 0
    c = fake_paho.last
    assert c.client_id == "mqttpi-node1-bms"
    assert c.last_payload("mqttpi/node1/bms/soc/state") == "80"
    assert "disconnect" in c.call_names()


def test_main_once_broker_unreachable(tmp_path, fake_paho, bms_serial, monkeypatch) -> None:
    monkeypatch.setattr(MqttConnection, "wait_connected", lambda self, timeout=None: False)
    cfg = tmp_path / "c.yaml"
    cfg.write_text(yaml.safe_dump(CFG))
    with pytest.raises(RuntimeError, match="not reachable"):
        bridge.main(["-c", str(cfg), "--once"])


def test_main_errors(tmp_path) -> None:
    assert bridge.main(["-c", str(tmp_path / "missing.yaml")]) == 1
    cfg = tmp_path / "c.yaml"
    cfg.write_text(yaml.safe_dump({**CFG, "bms": {"enabled": False}}))
    assert bridge.main(["-c", str(cfg)]) == 1


def test_bms_enabled() -> None:
    assert bms_enabled(CFG)
    assert not bms_enabled({})
    assert not bms_enabled({"bms": {"port": "/dev/x"}})


def test_subsystem_shared_polls_and_stops(fake_paho, bms_serial) -> None:
    conn = MqttConnection("b", client_id="mqttpi-node1", base_topic="mqttpi/node1")
    sub = BmsSubsystem(CFG, connection=conn)
    sub.start()
    c = fake_paho.last
    try:
        assert wait_until(lambda: c.last_payload("mqttpi/node1/bms/status") == "online")
        assert wait_until(lambda: bms_serial["opened"] >= 2)  # keeps polling
    finally:
        sub.stop()
    assert c.last_payload("mqttpi/node1/bms/status") == "offline"
    assert c.published_to("mqttpi/node1/status") == []  # node availability untouched
    assert len(fake_paho.instances) == 1


def test_subsystem_marks_bms_offline_on_poll_failure(fake_paho, bms_serial) -> None:
    bms_serial["silent"] = True
    conn = MqttConnection("b", client_id="mqttpi-node1", base_topic="mqttpi/node1")
    sub = BmsSubsystem(CFG, connection=conn)
    sub.start()
    try:
        assert wait_until(lambda: fake_paho.last.last_payload("mqttpi/node1/bms/status") == "offline")
        bms_serial["silent"] = False  # BMS comes back
        assert wait_until(lambda: fake_paho.last.last_payload("mqttpi/node1/bms/status") == "online")
    finally:
        sub.stop()


def test_run_bridge_until_signal(fake_paho, bms_serial, monkeypatch) -> None:
    handlers = {}
    monkeypatch.setattr(bridge.signal, "signal", lambda sig, h: handlers.__setitem__(sig, h))
    calls = {"n": 0}
    real = bridge.poll_once

    def poll(cfg, pub):
        calls["n"] += 1
        if calls["n"] == 2:
            handlers[bridge.signal.SIGTERM]()
            raise RuntimeError("poll failed")
        return real(cfg, pub)

    monkeypatch.setattr(bridge, "poll_once", poll)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    bridge.run_bridge({**CFG, "bms": {**CFG["bms"], "poll_interval": 0, "retry_delay": 0}})
    c = fake_paho.last
    assert calls["n"] == 2
    assert c.last_payload("mqttpi/node1/status") == "offline"
