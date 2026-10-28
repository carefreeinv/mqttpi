from __future__ import annotations

import json

from mqttpi.daemon import Daemon, base_topic_from, build_mqtt


CFG = {
    "device": {"id": "node1", "board": "pi4"},
    "mqtt": {
        "host": "broker",
        "base_topic": "mqttpi/node1",
        "keepalive": 20,
        "homeassistant": {"discovery": True},
    },
    "pins": [
        {"pin": 17, "alias": "relay_1", "direction": "output"},
        {"pin": 27, "alias": "door", "direction": "input"},
    ],
}


def test_base_topic_default_matches_docs() -> None:
    assert base_topic_from({"device": {"id": "abc"}}) == "mqttpi/abc"
    assert base_topic_from(CFG) == "mqttpi/node1"


def test_build_mqtt_sets_will_and_keepalive(fake_paho) -> None:
    conn = build_mqtt(CFG)
    assert conn.availability_topic == "mqttpi/node1/status"
    assert conn.keepalive == 20


def test_daemon_shutdown_publishes_offline(fake_paho) -> None:
    daemon = Daemon(CFG, mock_gpio=True)
    # Run the start-up half of Daemon.run without blocking on signals.
    daemon._mqtt = build_mqtt(CFG)
    daemon._mqtt.connect()
    client = fake_paho.last
    client.simulate_connect()
    daemon.shutdown()
    payloads = [p.payload for p in client.published_to("mqttpi/node1/status")]
    assert payloads == ["online", "offline"]


def test_gpio_discovery_includes_availability_topic(fake_paho) -> None:
    from mqttpi.gpio.manager import GpioManager

    conn = build_mqtt(CFG)
    manager = GpioManager(CFG, conn, mock_gpio=True)
    manager.start()
    try:
        client = fake_paho.last
        switch = json.loads(client.last_payload("homeassistant/switch/node1_relay_1/config"))
        sensor = json.loads(client.last_payload("homeassistant/binary_sensor/node1_door/config"))
        assert switch["availability_topic"] == "mqttpi/node1/status"
        assert sensor["availability_topic"] == "mqttpi/node1/status"
    finally:
        manager.stop()
