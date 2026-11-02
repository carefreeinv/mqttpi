"""Sensor subsystem: Reading, config parsing, scheduler, HA publisher, daemon wiring."""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

import pytest

from mqttpi.config import load_config
from mqttpi.daemon import Daemon, enabled_subsystems
from mqttpi.mqtt.discovery import DiscoveryLayout
from mqttpi.mqtt.factory import build_mqtt
from mqttpi.sensors import QUALITY_BAD, QUALITY_UNCERTAIN, Reading, SensorDriver, register_driver, unregister_driver
from mqttpi.sensors.config import parse_sensors, sensors_configured
from mqttpi.sensors.drivers.cpu_temperature import CpuTemperatureDriver
from mqttpi.sensors.ha_mqtt import NumericSensorPublisher
from mqttpi.sensors.model import EntitySpec
from mqttpi.sensors.scheduler import ScheduledSensor, SensorScheduler
from mqttpi.sensors.subsystem import SensorSubsystem
from tests.test_discovery import check, collect

ROOT = Path(__file__).resolve().parents[1]


class FakeDriver:
    """Returns queued readings / raises queued exceptions; blocks while ``gate`` is clear."""

    default_readings = {
        "temperature": {"unit_of_measurement": "°C", "device_class": "temperature",
                        "state_class": "measurement", "precision": 1, "name": "Temperature"},
        "humidity": {"unit_of_measurement": "%", "device_class": "humidity", "state_class": "measurement"},
    }

    def __init__(self, results: Optional[list] = None) -> None:
        self.results = list(results or [])
        self.calls = 0
        self.gate = threading.Event()
        self.gate.set()
        self.closed = False

    @classmethod
    def from_config(cls, spec):
        return cls([Reading({"temperature": 21.46, "humidity": 40.0})] * 1000)

    def read(self) -> Reading:
        self.calls += 1
        self.gate.wait(5)
        item = self.results.pop(0) if self.results else Reading({"temperature": 20.0})
        if isinstance(item, BaseException):
            raise item
        return item

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_type():
    register_driver("fake", FakeDriver.from_config, replace=True)
    yield "fake"
    unregister_driver("fake")


# -- Reading / EntitySpec -------------------------------------------------

def test_reading_numeric_and_quality() -> None:
    r = Reading({"a": 1, "b": None, "c": math.nan, "d": True, "e": "2.5", "f": "x", "g": math.inf})
    assert r.numeric() == {"a": 1.0, "e": 2.5}
    assert r.quality == "good" and r.timestamp > 0
    with pytest.raises(ValueError):
        Reading({"a": 1}, quality="meh")
    assert isinstance(FakeDriver(), SensorDriver)


def test_entity_format() -> None:
    e = EntitySpec("s", "k", "a", "A", precision=1)
    assert e.format(21.46) == "21.5" and e.format(3) == "3.0"
    assert EntitySpec("s", "k", "a", "A").format(3.0) == "3"
    assert EntitySpec("s", "k", "a", "A").format(0.25) == "0.25"


# -- config ----------------------------------------------------------------

def test_parse_mapping_with_driver_defaults(fake_type) -> None:
    [(sc, drv)] = parse_sensors({"sensors": {"env": {"type": "fake", "publish": {"interval_ms": 2000}}}})
    assert isinstance(drv, FakeDriver)
    assert (sc.interval_s, sc.timeout_s, sc.stale_after_s) == (2.0, 2.0, 10.0)
    assert [(e.alias, e.unit, e.device_class, e.precision) for e in sc.entities] == [
        ("env_temperature", "°C", "temperature", 1), ("env_humidity", "%", "humidity", None)]
    assert sc.entities[0].name == "Temperature"


def test_parse_list_form_and_overrides(fake_type) -> None:
    cfg = {"sensors": [{"name": "box", "chip": "fake", "timeout_s": 1, "stale_after_s": 99,
                        "publish": {"interval_ms": 60000, "retain": False},
                        "readings": {"temperature": {"alias": "box temp", "precision": 2,
                                                     "ha": {"name": "Box", "icon": "mdi:thermometer",
                                                            "expire_after": 600}}}}]}
    [(sc, _)] = parse_sensors(cfg)
    [e] = sc.entities
    assert (e.alias, e.name, e.unit, e.precision, e.icon, e.retain) == ("box_temp", "Box", "°C", 2, "mdi:thermometer",
                                                                        False)
    assert dict(e.extra) == {"expire_after": 600}
    assert (sc.timeout_s, sc.stale_after_s) == (1.0, 99.0)


def test_unknown_type_skipped_disabled_ignored(fake_type, caplog) -> None:
    caplog.set_level(logging.WARNING)
    out = parse_sensors({"sensors": {"lvl": {"chip": "mpu6050"}, "off": {"type": "fake", "enabled": False}}})
    assert out == [] and "no driver for type 'mpu6050'" in caplog.text
    assert not sensors_configured({"sensors": {"lvl": {"chip": "mpu6050"}}})
    assert sensors_configured({"sensors": {"x": {"type": "fake"}}})


def test_config_errors(fake_type) -> None:
    with pytest.raises(ValueError, match="missing 'type'"):
        parse_sensors({"sensors": {"x": {}}})
    with pytest.raises(ValueError, match="already used"):
        parse_sensors({"sensors": {"a": {"type": "fake", "readings": {"temperature": {"alias": "t"}}},
                                   "b": {"type": "fake", "readings": {"humidity": {"alias": "t"}}}}})
    with pytest.raises(ValueError, match="interval_ms"):
        parse_sensors({"sensors": {"a": {"type": "fake", "publish": {"interval_ms": 0}}}})


def test_documented_example_contract_parses(fake_type) -> None:
    """examples/robot.yaml documents sensors.<name>.{chip, publish, readings.<key>.{alias, ha}}."""
    register_driver("vl53l0x", lambda spec: FakeDriver(), replace=True)
    try:
        cfg = load_config(ROOT / "examples" / "robot.yaml")
        [(sc, _)] = parse_sensors(cfg)
        [e] = sc.entities
        assert (sc.name, sc.interval_s, e.key, e.alias, e.unit, e.device_class) == (
            "range", 0.2, "distance_mm", "front_range_mm", "mm", "distance")
        assert e.retain is False
    finally:
        unregister_driver("vl53l0x")


#: Examples whose sensors have built-in drivers (the rest document contracts ahead of drivers).
EXAMPLES_WITH_DRIVERS = {"sensors-i2c-onewire.yaml", "power-monitor.yaml"}


def test_examples_without_drivers_do_not_enable_sensors() -> None:
    for path in sorted((ROOT / "examples").rglob("*.yaml")):
        cfg = load_config(path)
        if cfg.get("sensors"):
            assert sensors_configured(cfg) == (path.name in EXAMPLES_WITH_DRIVERS), path


# -- cpu_temperature driver ----------------------------------------------

def test_cpu_temperature_driver(tmp_path) -> None:
    f = tmp_path / "temp"
    f.write_text("48312\n")
    [(sc, drv)] = parse_sensors({"sensors": {"cpu": {"type": "cpu_temperature", "path": str(f)}}})
    assert drv.read().values == {"temperature": 48.312}
    assert [(e.alias, e.unit, e.precision) for e in sc.entities] == [("cpu_temperature", "°C", 1)]
    with pytest.raises(FileNotFoundError):
        CpuTemperatureDriver(str(tmp_path / "missing")).read()


# -- scheduler -------------------------------------------------------------

class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def settle(sched: SensorScheduler, clock: Clock, pred: Callable[[], bool] = lambda: True,
           max_wait: float = 2.0) -> None:
    """tick until in-flight reads are collected (a hung read just waits out ``max_wait``)."""
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        sched.tick(clock.t)
        if all(s.inflight is None or (s.timed_out and not s.inflight.done()) for s in sched.sensors) and pred():
            return
        time.sleep(0.002)


def make(drivers: List[FakeDriver], interval=10.0, timeout=1.0, stale=30.0):
    clock = Clock()
    got, failed, stale_ev = [], [], []
    sensors = [ScheduledSensor(f"s{i}", d, interval, timeout, stale) for i, d in enumerate(drivers)]
    sched = SensorScheduler(sensors, on_reading=lambda s, r: got.append((s.name, r)),
                            on_failure=lambda s, why: failed.append((s.name, why)),
                            on_stale=lambda s: stale_ev.append(s.name), clock=clock)
    return sched, clock, got, failed, stale_ev


def test_scheduler_polls_at_interval() -> None:
    d = FakeDriver()
    sched, clock, got, _, _ = make([d], interval=10)
    for _ in range(5):
        settle(sched, clock)
        clock.t += 5  # two ticks per interval
    settle(sched, clock)
    assert d.calls == 3  # t=0, 10, 20
    assert len(got) == 3
    assert sched.tick(clock.t) == pytest.approx(1030.0)
    sched.stop()


def test_scheduler_timeout_does_not_stall_others() -> None:
    slow, fast = FakeDriver(), FakeDriver()
    slow.gate.clear()  # hangs
    sched, clock, got, failed, _ = make([slow, fast], interval=1, timeout=0.5, stale=100)
    for _ in range(4):
        settle(sched, clock, max_wait=0.05)
        clock.t += 1
    assert [n for n, _ in got].count("s1") >= 3
    assert failed == [("s0", "timeout after 0.5s")]
    assert slow.calls == 1  # not re-polled while hung
    slow.results = [Reading({"temperature": 99.0}), Reading({"temperature": 20.0})]
    slow.gate.set()  # the late 99.0 is discarded; polling resumes with a fresh read
    settle(sched, clock, lambda: "s0" in [n for n, _ in got])
    assert slow.calls == 2
    assert [r.values["temperature"] for n, r in got if n == "s0"] == [20.0]
    sched.stop()


def test_scheduler_failures_and_staleness() -> None:
    d = FakeDriver([Reading({"temperature": 1.0}), OSError("bus error"), Reading({"t": 1}, quality=QUALITY_BAD),
                    Reading({"temperature": None}), OSError("x"), Reading({"temperature": 2.0})])
    sched, clock, got, failed, stale = make([d], interval=10, stale=30)
    settle(sched, clock)
    assert len(got) == 1 and not sched.sensors[0].stale
    for _ in range(3):
        clock.t += 10
        settle(sched, clock)
    assert [w for _, w in failed] == ["OSError: bus error", "bad or empty reading", "bad or empty reading"]
    assert stale == ["s0"] and sched.sensors[0].stale  # 30 s since last good
    clock.t += 10
    settle(sched, clock)
    assert stale == ["s0"]  # reported once
    clock.t += 10
    settle(sched, clock)
    assert len(got) == 2 and not sched.sensors[0].stale  # recovered
    sched.stop()


def test_scheduler_never_good_goes_stale_from_start() -> None:
    d = FakeDriver([OSError("x")] * 10)
    sched, clock, _, _, stale = make([d], interval=10, stale=25)
    for _ in range(3):
        settle(sched, clock)
        clock.t += 10
    settle(sched, clock)
    assert stale == ["s0"]
    sched.stop()


def test_scheduler_thread_runs_real_time() -> None:
    d = FakeDriver()
    got = []
    sched = SensorScheduler([ScheduledSensor("s", d, 0.05, 1, 10)], on_reading=lambda s, r: got.append(r))
    sched.start()
    deadline = time.monotonic() + 3
    while len(got) < 3 and time.monotonic() < deadline:
        time.sleep(0.01)
    sched.stop()
    assert len(got) >= 3


# -- HA publisher ----------------------------------------------------------

CFG = {
    "device": {"id": "node1", "board": "pi4", "ha": {"name": "Test Node"}},
    "mqtt": {"host": "b", "base_topic": "mqttpi/node1", "homeassistant": {"discovery": True}},
    "sensors": {"env": {"type": "fake", "publish": {"interval_ms": 1000},
                        "readings": {"temperature": {"alias": "enclosure_temp", "ha": {"name": "Enclosure"}},
                                     "humidity": {}}}},
}


def test_sensor_discovery_snapshot(fake_paho, fake_type) -> None:
    conn = build_mqtt(CFG)
    sub = SensorSubsystem(CFG, conn)
    sub.publisher.publish_discovery(sub.entities)
    payloads = collect(fake_paho.last)
    assert set(payloads) == {"homeassistant/sensor/node1_enclosure_temp/config",
                             "homeassistant/sensor/node1_env_humidity/config"}
    t = payloads["homeassistant/sensor/node1_enclosure_temp/config"]
    assert (t["unit_of_measurement"], t["device_class"], t["state_class"]) == ("°C", "temperature", "measurement")
    assert t["availability"] == [{"topic": "mqttpi/node1/status"},
                                 {"topic": "mqttpi/node1/sensors/enclosure_temp/availability"}]
    assert t["availability_mode"] == "all"
    assert t["device"]["identifiers"] == ["node1"]  # same HA device as the GPIO entities
    check("sensor_discovery", payloads)


def test_publisher_node_layout() -> None:
    class Rec:
        def __init__(self):
            self.msgs = []

        def publish(self, topic, payload, retain=None):
            self.msgs.append((topic, payload, retain))

    rec = Rec()
    pub = NumericSensorPublisher(rec, "mqttpi/n1", "n1", {"identifiers": ["n1"]},
                                 layout=DiscoveryLayout(node_id="n1"))
    e = EntitySpec("s", "temperature", "t1", "T1")
    pub.publish_discovery([e])
    assert [m[0] for m in rec.msgs] == ["homeassistant/sensor/n1_t1/config", "homeassistant/sensor/n1/t1/config"]
    assert rec.msgs[0][1] == "" and rec.msgs[0][2] is True


# -- subsystem end to end (fake MQTT) ---------------------------------------

def test_subsystem_publishes_state_attributes_availability(fake_paho, fake_type) -> None:
    clock = Clock()
    conn = build_mqtt(CFG)
    drv = FakeDriver([Reading({"temperature": 21.46, "humidity": 40}, timestamp=0, quality=QUALITY_UNCERTAIN)])
    sc = parse_sensors(CFG)[0][0]
    sub = SensorSubsystem(CFG, conn, sensors=[(sc, drv)], clock=clock)
    conn.connect()
    client = fake_paho.last
    client.simulate_connect()
    sub.mqtt.add_connect_callback(sub.announce)
    sub.announce()
    base = "mqttpi/node1/sensors"
    assert client.last_payload(f"{base}/enclosure_temp/availability") == "offline"  # no reading yet

    settle(sub.scheduler, clock)
    assert client.last_payload(f"{base}/enclosure_temp/state") == "21.5"
    assert client.last_payload(f"{base}/env_humidity/state") == "40"
    assert json.loads(client.last_payload(f"{base}/enclosure_temp/attributes")) == {
        "timestamp": "1970-01-01T00:00:00+00:00", "quality": "uncertain"}
    assert client.last_payload(f"{base}/enclosure_temp/availability") == "online"
    assert client.published_to(f"{base}/enclosure_temp/availability")[-1].retain

    drv.results = [OSError("gone")] * 20
    for _ in range(12):
        clock.t += 1
        settle(sub.scheduler, clock)
    assert client.last_payload(f"{base}/enclosure_temp/availability") == "offline"  # stale after 10 s

    # reconnect re-announces discovery + current availability
    n = len(client.published)
    client.simulate_disconnect()
    client.simulate_connect()
    topics = [p.topic for p in client.published[n:]]
    assert "homeassistant/sensor/node1_enclosure_temp/config" in topics
    sub.stop()
    assert drv.closed


def test_daemon_runs_sensor_only_config(fake_paho, fake_type) -> None:
    cfg = json.loads(json.dumps(CFG))
    cfg["sensors"]["env"]["publish"]["interval_ms"] = 50
    assert enabled_subsystems(cfg) == ["sensors"]
    daemon = Daemon(cfg)
    t = threading.Thread(target=daemon.run, daemon=True)
    t.start()
    deadline = time.monotonic() + 3
    while not (fake_paho.instances and daemon.sensors) and time.monotonic() < deadline:
        time.sleep(0.01)
    client = fake_paho.last
    client.simulate_connect()
    while client.last_payload("mqttpi/node1/sensors/enclosure_temp/state") is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert client.last_payload("mqttpi/node1/sensors/enclosure_temp/state") == "21.5"
    assert client.last_payload("homeassistant/sensor/node1_enclosure_temp/config")
    daemon.stop()
    t.join(timeout=5)
    assert not t.is_alive()
    assert client.last_payload("mqttpi/node1/status") == "offline"
