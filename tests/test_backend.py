from __future__ import annotations

import builtins
import logging
import sys

import pytest

from mqttpi.daemon import main
from mqttpi.gpio import backend as backend_mod
from mqttpi.gpio.backend import (
    GpioBackendUnavailable,
    MockGpioBackend,
    create_backend,
)
from mqttpi.gpio.manager import GpioManager
from mqttpi.mqtt.client import MqttConnection


@pytest.fixture
def no_rpi_gpio(monkeypatch):
    """Make ``import RPi.GPIO`` fail, as on a machine without the library."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "RPi" or name.startswith("RPi."):
            raise ImportError("No module named 'RPi'")
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "RPi", raising=False)
    monkeypatch.delitem(sys.modules, "RPi.GPIO", raising=False)
    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_missing_library_raises_by_default(no_rpi_gpio) -> None:
    with pytest.raises(GpioBackendUnavailable) as err:
        create_backend()
    assert "--mock-gpio" in str(err.value)
    assert isinstance(err.value, RuntimeError)


def test_init_failure_raises(monkeypatch) -> None:
    def boom(self):
        raise RuntimeError("Cannot determine SOC peripheral base address")

    monkeypatch.setattr(backend_mod.RPiGpioBackend, "__init__", boom)
    with pytest.raises(GpioBackendUnavailable, match="SOC peripheral"):
        create_backend()


def test_non_strict_keeps_old_fallback(no_rpi_gpio, caplog) -> None:
    with caplog.at_level(logging.WARNING):
        be = create_backend(strict=False)
    assert isinstance(be, MockGpioBackend)
    assert "using mock" in caplog.text


def test_force_mock_and_config_mock(no_rpi_gpio) -> None:
    assert isinstance(create_backend(force_mock=True), MockGpioBackend)
    assert isinstance(create_backend(backend="mock"), MockGpioBackend)


def test_unknown_backend_name_rejected() -> None:
    with pytest.raises(ValueError, match="gpio.backend"):
        create_backend(backend="wiringpi")


CFG = {
    "device": {"id": "unit", "board": "rpi4"},
    "pins": [{"alias": "relay_1", "pin": 17, "direction": "output"}],
}


def test_manager_exposes_backend_name(fake_paho, caplog) -> None:
    conn = MqttConnection("broker", base_topic="mqttpi/unit")
    with caplog.at_level(logging.INFO):
        mgr = GpioManager(CFG, conn, mock_gpio=True)
    assert mgr.backend_name == "mock"
    assert "GPIO backend: mock (board: rpi4)" in caplog.text


def test_manager_honors_config_backend_mock(fake_paho, no_rpi_gpio) -> None:
    conn = MqttConnection("broker", base_topic="mqttpi/unit")
    mgr = GpioManager({**CFG, "gpio": {"backend": "mock"}}, conn)
    assert mgr.backend_name == "mock"


def test_daemon_exits_nonzero_without_gpio_library(tmp_path, fake_paho, no_rpi_gpio, caplog) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "device: {id: unit}\n"
        "mqtt: {host: 127.0.0.1}\n"
        "pins:\n  - {alias: relay_1, pin: 17, direction: output}\n"
    )
    with caplog.at_level(logging.ERROR):
        rc = main(["-c", str(cfg), "-s", str(tmp_path / "none.yaml")])
    assert rc == 1
    assert "GPIO backend 'rpi' unavailable" in caplog.text


def test_mock_input_idle_level_follows_pull() -> None:
    be = MockGpioBackend()
    be.setup_input(1, "up")
    be.setup_input(2, "down")
    be.setup_input(3, None)
    assert (be.read(1), be.read(2), be.read(3)) == (True, False, False)
