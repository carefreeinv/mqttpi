"""pwm_output: backend channels (mock, software, sysfs), manager, discovery, filters."""

from __future__ import annotations

import json
import logging

import pytest

from mqttpi.gpio.commands import CommandDecision, clamp_duty, mutually_exclusive
from mqttpi.gpio.ha_mqtt import format_duty
from mqttpi.gpio.manager import GpioManager
from mqttpi.gpio.pins import parse_pins
from mqttpi.gpio.pwm import MockPwm, SoftwarePwm, SysfsPwm, hardware_channel
from mqttpi.mqtt.factory import build_mqtt
from tests.test_discovery import check, collect
from tests.test_gpio_manager import make_cfg, started  # noqa: F401 (fixture)

FAN = {"pin": 18, "alias": "fan", "direction": "pwm_output", "frequency_hz": 25000, "initial_duty": 0,
       "ha": {"name": "Fan Speed", "min": 0, "max": 100, "step": 1, "unit_of_measurement": "%", "icon": "mdi:fan"}}


# -- config ----------------------------------------------------------------

def test_parse_pwm_defaults_and_contract() -> None:
    [p] = parse_pins({"pins": [{"pin": 13, "alias": "dim", "direction": "pwm_output"}]})
    assert (p.frequency_hz, p.initial_duty, p.pwm_mode, p.ha_min, p.ha_max, p.ha_step, p.ha_unit) == (
        1000.0, 0.0, "software", 0.0, 100.0, 1.0, "%")
    [f] = parse_pins({"pins": [FAN]})
    assert (f.frequency_hz, f.ha_icon, f.is_pwm) == (25000.0, "mdi:fan", True)


@pytest.mark.parametrize("bad, match", [
    ({"frequency_hz": 0}, "frequency_hz"),
    ({"pwm_mode": "turbo"}, "pwm_mode"),
    ({"ha": {"min": 50, "max": 40}}, "min/max"),
    ({"ha": {"max": 150}}, "min/max"),
    ({"initial_duty": 90, "ha": {"max": 80}}, "initial_duty"),
])
def test_parse_pwm_errors(bad, match) -> None:
    with pytest.raises(ValueError, match=match):
        parse_pins({"pins": [{"pin": 13, "alias": "x", "direction": "pwm_output", **bad}]})


def test_format_duty() -> None:
    assert [format_duty(v) for v in (0, 40.0, 12.5, 33.333)] == ["0", "40", "12.5", "33.33"]


# -- channels ----------------------------------------------------------------

def test_mock_pwm_clamps() -> None:
    ch = MockPwm(18, 1000, 150)
    assert ch.duty == 100
    ch.set_duty(-3)
    assert ch.duty == 0
    ch.stop()
    assert not ch.running


class FakeRpiGpio:
    OUT, LOW = "out", 0

    def __init__(self):
        self.calls = []

    def setup(self, pin, mode, initial=None):
        self.calls.append(("setup", pin, mode, initial))

    def PWM(self, pin, freq):  # noqa: N802 - RPi.GPIO API
        gpio = self

        class P:
            def start(self, d):
                gpio.calls.append(("start", pin, freq, d))

            def ChangeDutyCycle(self, d):  # noqa: N802
                gpio.calls.append(("duty", d))

            def ChangeFrequency(self, f):  # noqa: N802
                gpio.calls.append(("freq", f))

            def stop(self):
                gpio.calls.append(("stop",))
        return P()


def test_software_pwm_wraps_rpi_gpio(caplog) -> None:
    g = FakeRpiGpio()
    caplog.set_level(logging.WARNING)
    ch = SoftwarePwm(g, 12, 25000, 10)
    assert "inaccurate" in caplog.text
    ch.set_duty(120)
    ch.set_frequency(500)
    ch.stop()
    assert g.calls == [("setup", 12, "out", 0), ("start", 12, 25000.0, 10.0), ("duty", 100.0), ("freq", 500.0),
                       ("stop",)]


def fake_sysfs(tmp_path, chip=0, channel=0):
    """Fake /sys/class/pwm where 'export' creates the channel directory."""
    chip_dir = tmp_path / f"pwmchip{chip}"
    chip_dir.mkdir()
    ch = chip_dir / f"pwm{channel}"
    ch.mkdir()  # pre-created (as if already exported)
    for name in ("period", "duty_cycle", "enable"):
        (ch / name).write_text("0\n")
    (chip_dir / "export").write_text("")
    (chip_dir / "unexport").write_text("")
    return ch


def test_sysfs_pwm(tmp_path) -> None:
    ch_dir = fake_sysfs(tmp_path, channel=1)
    ch = SysfsPwm(0, 1, 1000, 25, root=tmp_path)
    read = lambda n: (ch_dir / n).read_text().strip()  # noqa: E731
    assert (read("period"), read("duty_cycle"), read("enable")) == ("1000000", "250000", "1")
    ch.set_frequency(25000)
    assert (read("period"), read("duty_cycle")) == ("40000", "10000")
    ch.set_duty(100)
    assert read("duty_cycle") == "40000"
    ch.stop()
    assert (read("duty_cycle"), read("enable"), (tmp_path / "pwmchip0" / "unexport").read_text().strip()) == (
        "0", "0", "1")


def test_sysfs_pwm_missing_chip_or_channel(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="dtoverlay"):
        SysfsPwm(0, 0, 1000, root=tmp_path)
    (tmp_path / "pwmchip0").mkdir()
    (tmp_path / "pwmchip0" / "export").write_text("")
    with pytest.raises(RuntimeError, match="did not appear"):
        SysfsPwm(0, 0, 1000, root=tmp_path, export_timeout_s=0.05)
    assert (tmp_path / "pwmchip0" / "export").read_text().strip() == "0"


def test_hardware_channel_maps() -> None:
    assert hardware_channel("pi4", 18)[0] == 0 and hardware_channel("pi4", 19)[0] == 1
    assert hardware_channel("pi5", 18)[0] == 2 and hardware_channel("pi5", 19)[0] == 3
    assert hardware_channel("pi4", 5, explicit=1)[0] == 1
    with pytest.raises(ValueError, match="no hardware PWM"):
        hardware_channel("pizero", 17)


# -- manager -------------------------------------------------------------------

def test_pwm_start_state_and_set(started) -> None:  # noqa: F811
    mgr, client = started([dict(FAN, initial_duty=20)])
    ch = mgr.backend.pwm[18]
    assert (ch.frequency_hz, ch.duty) == (25000.0, 20.0)
    assert "mqttpi/n/gpio/fan/set" in [t for t, _q in client.subscriptions]
    assert client.last_payload("mqttpi/n/gpio/fan/state") == "20"
    client.simulate_message("mqttpi/n/gpio/fan/set", "42.5")
    assert ch.duty == 42.5 and client.last_payload("mqttpi/n/gpio/fan/state") == "42.5"
    client.simulate_message("mqttpi/n/gpio/fan/set", "OFF")
    assert ch.duty == 0
    client.simulate_message("mqttpi/n/gpio/fan/set", "ON")
    assert ch.duty == 100
    for junk in ("fast", "nan", "inf"):
        client.simulate_message("mqttpi/n/gpio/fan/set", junk)
    assert ch.duty == 100
    client.simulate_message("mqttpi/n/gpio/fan/set", "250")
    assert ch.duty == 100  # clamped to ha.max
    assert mgr.states()["fan"] == 100 and mgr.duty("fan") == 100


def test_pwm_min_clamp_and_invert(started) -> None:  # noqa: F811
    mgr, client = started([dict(FAN, invert=True, ha={"min": 20, "max": 80})])
    ch = mgr.backend.pwm[18]
    assert ch.duty == 100  # logical 0 % on an active-low driver
    assert mgr.request_duty("fan", 5) == 20  # below min → min
    assert ch.duty == 80
    assert mgr.request_duty("fan", 0) == 0  # 0 = off is always allowed
    assert mgr.request_duty("fan", 95) == 80
    with pytest.raises(KeyError):
        mgr.request_duty("nope", 1)


def test_pwm_stop_sets_zero(started) -> None:  # noqa: F811
    mgr, _client = started([dict(FAN, initial_duty=60)])
    ch = mgr.backend.pwm[18]
    mgr.stop()
    assert ch.duty == 0 and not ch.running


def test_pwm_commands_pass_filters(started) -> None:  # noqa: F811
    mgr, client = started([dict(FAN), dict(FAN, pin=19, alias="pump")])
    mgr.add_command_filter(clamp_duty("fan", 0, 70))
    seen = []
    mgr.add_command_filter(lambda req: seen.append((req.alias, req.value, req.current)))
    client.simulate_message("mqttpi/n/gpio/fan/set", "90")
    assert mgr.duty("fan") == 70 and client.last_payload("mqttpi/n/gpio/fan/state") == "70"
    assert seen[-1] == ("fan", 70.0, 0.0)  # later filters see the clamped value
    mgr.add_command_filter(lambda req: CommandDecision.reject("maintenance") if req.alias == "pump" else None)
    client.simulate_message("mqttpi/n/gpio/pump/set", "50")
    assert mgr.duty("pump") == 0 and client.last_payload("mqttpi/n/gpio/pump/state") == "0"


def test_pwm_interlock_with_mutually_exclusive(started) -> None:  # noqa: F811
    """Speed-controlled actuator: extend and retract PWM channels never both > 0 %."""
    mgr, _client = started([dict(FAN, pin=12, alias="extend"), dict(FAN, pin=13, alias="retract")])
    mgr.add_command_filter(mutually_exclusive("extend", "retract"))
    assert mgr.request_duty("extend", 60) == 60
    assert mgr.request_duty("retract", 40) == 0  # rejected while extend > 0
    assert mgr.request_duty("extend", 0) == 0
    assert mgr.request_duty("retract", 40) == 40


def test_filter_returning_non_numeric_duty_rejects(started) -> None:  # noqa: F811
    mgr, _client = started([dict(FAN)])
    mgr.add_command_filter(lambda req: CommandDecision.modify("lots"))
    assert mgr.request_duty("fan", 30) == 0


def test_clamp_duty_validation() -> None:
    with pytest.raises(ValueError):
        clamp_duty("x", 80, 20)


def test_pwm_only_config_enables_gpio(fake_paho) -> None:
    cfg = make_cfg([FAN])
    mgr = GpioManager(cfg, build_mqtt(cfg), mock_gpio=True)
    assert [p.alias for p in mgr.pins] == ["fan"]


def test_number_discovery_snapshot(started) -> None:  # noqa: F811
    mgr, client = started([FAN])
    payloads = collect(client)
    n = payloads["homeassistant/number/n_fan/config"]
    assert (n["min"], n["max"], n["step"], n["unit_of_measurement"], n["mode"]) == (0, 100, 1, "%", "slider")
    assert n["command_topic"] == "mqttpi/n/gpio/fan/set" and n["state_topic"] == "mqttpi/n/gpio/fan/state"
    check("pwm_number_discovery", payloads)
    json.dumps(n)
