from __future__ import annotations

import json
import logging

import pytest

from mqttpi.daemon import Daemon, build_mqtt
from mqttpi.gpio.manager import GpioManager
from mqttpi.mqtt.client import MqttConnection

CFG = {
    "device": {"id": "node1", "board": "pi4"},
    "mqtt": {"host": "broker", "base_topic": "mqttpi/node1"},
    "pins": [
        {"pin": 17, "alias": "relay_1", "direction": "output"},
        {"pin": 27, "alias": "door", "direction": "input"},
    ],
}


def test_connect_is_async_with_backoff_and_queue_bound(fake_paho) -> None:
    conn = MqttConnection("broker", base_topic="b", reconnect_min_s=2, reconnect_max_s=30,
                          max_queued_messages=50)
    conn.connect()
    client = fake_paho.last
    names = client.call_names()
    assert "connect" not in names  # never the blocking connect
    assert names.index("will_set") < names.index("connect_async") < names.index("loop_start")
    assert ("reconnect_delay_set", (2, 30), {}) in client.calls
    assert ("max_queued_messages_set", (50,), {}) in client.calls
    assert conn.is_connected is False


def test_connect_does_not_raise_when_broker_down(fake_paho) -> None:
    conn = MqttConnection("broker", base_topic="b")
    conn.connect()
    fake_paho.last.on_connect_fail(fake_paho.last, None)  # paho retry failure
    conn.publish("b/x", "1")  # must not raise or block
    assert conn.wait_connected(timeout=0.01) is False


def test_defaults(fake_paho) -> None:
    conn = MqttConnection("broker")
    assert (conn.reconnect_min_s, conn.reconnect_max_s, conn.max_queued_messages) == (1, 60, 1000)


@pytest.mark.parametrize("kwargs", [
    {"host": ""},
    {"host": "bad host"},
    {"host": "mqtt://broker"},
    {"host": "broker", "port": 0},
    {"host": "broker", "port": 70000},
    {"host": "broker", "reconnect_min_s": 0},
    {"host": "broker", "reconnect_min_s": 10, "reconnect_max_s": 5},
    {"host": "broker", "max_queued_messages": -1},
])
def test_configuration_errors_fail_fast(fake_paho, kwargs) -> None:
    with pytest.raises(ValueError):
        MqttConnection(**kwargs)


def test_subscriptions_reissued_after_reconnect(fake_paho) -> None:
    conn = MqttConnection("broker", base_topic="b")
    conn.connect()
    conn.subscribe("b/gpio/x/set")  # before connect: remembered, not sent
    client = fake_paho.last
    assert client.subscriptions == []
    client.simulate_connect()
    client.simulate_disconnect()
    client.simulate_connect()
    assert client.subscriptions == [("b/gpio/x/set", 1), ("b/gpio/x/set", 1)]


def test_subscribe_while_connected_is_immediate(fake_paho) -> None:
    conn = MqttConnection("broker", base_topic="b")
    conn.connect()
    fake_paho.last.simulate_connect()
    conn.subscribe("t")
    conn.subscribe("t")  # dedup in the remembered list
    assert fake_paho.last.subscriptions == [("t", 1), ("t", 1)]
    fake_paho.last.simulate_connect()
    assert fake_paho.last.subscriptions.count(("t", 1)) == 3


def test_one_warning_per_outage(fake_paho, caplog) -> None:
    conn = MqttConnection("broker", base_topic="b")
    conn.connect()
    client = fake_paho.last
    caplog.set_level(logging.DEBUG, logger="mqttpi.mqtt.client")
    for _ in range(5):
        client.on_connect_fail(client, None)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    caplog.clear()
    client.simulate_connect()
    client.simulate_disconnect(rc=7)
    client.on_connect_fail(client, None)
    client.on_connect_fail(client, None)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1  # the new outage, once


def test_warns_again_after_many_failed_attempts(fake_paho, caplog) -> None:
    conn = MqttConnection("broker", base_topic="b")
    conn.connect()
    caplog.set_level(logging.WARNING, logger="mqttpi.mqtt.client")
    for _ in range(12):
        fake_paho.last.on_connect_fail(fake_paho.last, None)
    assert len(caplog.records) == 2
    assert "check mqtt.host" in caplog.records[1].getMessage()


def test_build_mqtt_reads_reconnect_keys(fake_paho) -> None:
    cfg = dict(CFG, mqtt=dict(CFG["mqtt"], reconnect_min_s=3, reconnect_max_s=9,
                              max_queued_messages=7))
    conn = build_mqtt(cfg)
    assert (conn.reconnect_min_s, conn.reconnect_max_s, conn.max_queued_messages) == (3, 9, 7)


def test_gpio_starts_before_broker_and_announces_on_each_connect(fake_paho) -> None:
    conn = build_mqtt(CFG)
    manager = GpioManager(CFG, conn, mock_gpio=True)
    conn.connect()
    manager.start()  # broker not connected yet: hardware configured anyway
    client = fake_paho.last
    try:
        assert manager.backend.read(17) is False
        disc = "homeassistant/switch/node1_relay_1/config"
        assert client.published_to(disc) == []
        client.simulate_connect()
        assert len(client.published_to(disc)) == 1
        assert ("mqttpi/node1/gpio/relay_1/set", 1) in client.subscriptions
        # Broker restart without persistence: discovery + state re-published.
        client.simulate_disconnect()
        client.simulate_connect()
        assert len(client.published_to(disc)) == 2
        assert len(client.published_to("mqttpi/node1/gpio/relay_1/state")) == 2
        assert client.subscriptions.count(("mqttpi/node1/gpio/relay_1/set", 1)) == 2
    finally:
        manager.stop()


def test_discovery_default_on_without_homeassistant_block(fake_paho) -> None:
    conn = build_mqtt(CFG)  # CFG has no mqtt.homeassistant mapping
    manager = GpioManager(CFG, conn, mock_gpio=True)
    conn.connect()
    manager.start()
    try:
        fake_paho.last.simulate_connect()
        payload = fake_paho.last.last_payload("homeassistant/switch/node1_relay_1/config")
        assert json.loads(payload)["command_topic"] == "mqttpi/node1/gpio/relay_1/set"
    finally:
        manager.stop()


def test_discovery_can_be_disabled(fake_paho) -> None:
    cfg = dict(CFG, mqtt=dict(CFG["mqtt"], homeassistant={"discovery": False}))
    conn = build_mqtt(cfg)
    manager = GpioManager(cfg, conn, mock_gpio=True)
    conn.connect()
    manager.start()
    try:
        fake_paho.last.simulate_connect()
        assert not [p for p in fake_paho.last.published if p.topic.startswith("homeassistant/")]
    finally:
        manager.stop()


def test_daemon_main_rejects_bad_host(tmp_path, fake_paho) -> None:
    from mqttpi.daemon import main

    cfg = tmp_path / "c.yaml"
    cfg.write_text("mqtt: {host: 'bad host'}\npins: [{pin: 1, alias: a}]\n")
    assert main(["-c", str(cfg), "--mock-gpio"]) == 1


def test_daemon_object_still_constructs(fake_paho) -> None:
    assert Daemon(CFG, mock_gpio=True).cfg is CFG
