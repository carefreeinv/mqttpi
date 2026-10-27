"""Daemon smoke run (mock GPIO, fake MQTT client) and example config loading."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from mqttpi.bms.bridge import build_publisher
from mqttpi.config import load_config
from mqttpi.daemon import Daemon, main
from mqttpi.gpio.manager import GpioManager
from mqttpi.mqtt.factory import build_mqtt

ROOT = Path(__file__).resolve().parents[1]
# Examples documented as implemented (daemon.md "Supported examples today",
# plus the linear actuator example).
GPIO_EXAMPLES = ["relay-bank-16.yaml", "linear-actuator.yaml"]
BMS_EXAMPLES = ["jbd-bms.yaml"]


def wait_until(pred, timeout=3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.01)
    return pred()


def test_daemon_runs_and_stops_cleanly(fake_paho) -> None:
    cfg = load_config(ROOT / "examples" / "relay-bank-16.yaml")
    cfg["mqtt"]["host"] = "broker"
    daemon = Daemon(cfg, mock_gpio=True)
    t = threading.Thread(target=daemon.run, daemon=True)
    t.start()
    assert wait_until(lambda: fake_paho.instances and daemon.gpio is not None)
    client = fake_paho.last
    client.simulate_connect()
    base = daemon.gpio.publisher.base_topic
    assert wait_until(lambda: client.last_payload(f"{base}/status") == "online")
    alias = daemon.gpio.pins[0].alias
    client.simulate_message(f"{base}/gpio/{alias}/set", "ON")
    assert client.last_payload(f"{base}/gpio/{alias}/state") == "ON"
    daemon.stop()
    t.join(timeout=5)
    assert not t.is_alive()
    assert client.last_payload(f"{base}/status") == "offline"
    assert len(fake_paho.instances) == 1


def test_daemon_without_subsystems_errors() -> None:
    with pytest.raises(RuntimeError, match="No enabled subsystems"):
        Daemon({"mqtt": {"host": "b"}}).run()


def test_main_missing_config_returns_error(tmp_path) -> None:
    assert main(["-c", str(tmp_path / "missing.yaml")]) != 0


@pytest.mark.parametrize("name", GPIO_EXAMPLES)
def test_gpio_examples_load(name, fake_paho) -> None:
    cfg = load_config(ROOT / "examples" / name, ROOT / "secrets.example.yaml")
    mgr = GpioManager(cfg, build_mqtt(cfg), mock_gpio=True)
    assert mgr.pins
    mgr.start()
    mgr.stop()


@pytest.mark.parametrize("name", BMS_EXAMPLES)
def test_bms_examples_load(name, fake_paho) -> None:
    cfg = load_config(ROOT / "examples" / name, ROOT / "secrets.example.yaml")
    assert cfg["bms"]["enabled"]
    pub = build_publisher(cfg)
    assert pub.device_id


def test_every_example_yaml_parses() -> None:
    for path in sorted((ROOT / "examples").rglob("*.yaml")):
        cfg = load_config(path)
        assert isinstance(cfg, dict) and cfg, path


@pytest.mark.parametrize("module", ["mqttpi", "mqttpi.bms"])
def test_python_dash_m_entry_points(module, monkeypatch, capsys) -> None:
    import runpy
    import sys

    monkeypatch.setattr(sys, "argv", [module, "--help"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module(module, run_name="__main__")
    assert exc.value.code == 0
    assert "usage" in capsys.readouterr().out
