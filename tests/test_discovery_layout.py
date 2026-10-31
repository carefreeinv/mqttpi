from __future__ import annotations

import json

import pytest

from mqttpi.bms.bridge import build_publisher
from mqttpi.gpio.manager import GpioManager
from mqttpi.mqtt.client import MqttConnection
from mqttpi.mqtt.discovery import DiscoveryLayout, parse_discovery_layout
from mqttpi.mqtt.factory import build_mqtt

PINS = [
    {"pin": 17, "alias": "relay_1", "direction": "output"},
    {"pin": 27, "alias": "door", "direction": "input"},
]


def cfg(**ha):
    return {
        "device": {"id": "node1", "board": "pi4"},
        "mqtt": {"host": "b", "base_topic": "mqttpi/node1",
                 "homeassistant": {"discovery": True, **ha}},
        "pins": PINS,
        "bms": {"enabled": True, "port": "/dev/ttyUSB0"},
    }


def gpio_discovery(c, fake_paho):
    conn = build_mqtt(c)
    mgr = GpioManager(c, conn, mock_gpio=True)
    mgr.publisher.publish_discovery(mgr.pins)
    return fake_paho.last


def config_topics(client):
    return [p.topic for p in client.published if p.topic.endswith("/config") and p.payload]


def cleared_topics(client):
    return [p.topic for p in client.published if p.topic.endswith("/config") and not p.payload]


# --- helper -----------------------------------------------------------------

def test_flat_layout_is_default() -> None:
    layout = parse_discovery_layout(cfg())
    assert layout == DiscoveryLayout()
    assert layout.topic("switch", "node1", "relay_1") == "homeassistant/switch/node1_relay_1/config"
    assert layout.stale_topics("switch", "node1", "relay_1") == []


def test_node_layout_true_uses_device_id() -> None:
    layout = parse_discovery_layout(cfg(discovery_node_id=True))
    assert layout.node_id == "node1"
    assert layout.topic("switch", "node1", "relay_1") == "homeassistant/switch/node1/relay_1/config"
    # another logical device on the node keeps its prefix in the object id
    assert layout.topic("sensor", "jbd_x", "soc") == "homeassistant/sensor/node1/jbd_x_soc/config"
    assert layout.stale_topics("switch", "node1", "relay_1") == [
        "homeassistant/switch/node1_relay_1/config"]


def test_node_layout_explicit_and_sanitized() -> None:
    assert parse_discovery_layout(cfg(discovery_node_id="garage-2")).node_id == "garage-2"
    c = cfg(discovery_node_id=True)
    c["device"]["id"] = "my.node 1"
    assert parse_discovery_layout(c).node_id == "my_node_1"
    with pytest.raises(ValueError):
        parse_discovery_layout(cfg(discovery_node_id="bad/id"))
    with pytest.raises(ValueError):
        parse_discovery_layout(cfg(discovery_node_id=3))


def test_custom_prefix_and_no_cleanup() -> None:
    layout = parse_discovery_layout(cfg(discovery_prefix="ha/", discovery_node_id=True,
                                        discovery_clear_legacy=False))
    assert layout.topic("switch", "node1", "a") == "ha/switch/node1/a/config"
    assert layout.stale_topics("switch", "node1", "a") == []


# --- GPIO -------------------------------------------------------------------

def test_gpio_default_layout_unchanged(fake_paho) -> None:
    client = gpio_discovery(cfg(), fake_paho)
    assert sorted(config_topics(client)) == [
        "homeassistant/binary_sensor/node1_door/config",
        "homeassistant/switch/node1_relay_1/config",
    ]
    assert cleared_topics(client) == []


def test_gpio_node_layout_clears_legacy_first_and_keeps_unique_ids(fake_paho) -> None:
    flat = gpio_discovery(cfg(), fake_paho)
    flat_ids = sorted(json.loads(p.payload)["unique_id"] for p in flat.published
                      if p.topic.endswith("/config"))
    client = gpio_discovery(cfg(discovery_node_id=True), fake_paho)
    assert sorted(config_topics(client)) == [
        "homeassistant/binary_sensor/node1/door/config",
        "homeassistant/switch/node1/relay_1/config",
    ]
    topics = [p.topic for p in client.published if p.topic.endswith("/config")]
    legacy = "homeassistant/switch/node1_relay_1/config"
    assert topics.index(legacy) < topics.index("homeassistant/switch/node1/relay_1/config")
    assert all(p.retain for p in client.published if p.topic in cleared_topics(client))
    ids = sorted(json.loads(p.payload)["unique_id"] for p in client.published
                 if p.topic.endswith("/config") and p.payload)
    assert ids == flat_ids


def test_clear_is_retained_even_when_mqtt_retain_false(fake_paho) -> None:
    c = cfg(discovery_node_id=True)
    c["mqtt"]["retain"] = False
    client = gpio_discovery(c, fake_paho)
    clears = [p for p in client.published if p.topic.endswith("/config") and not p.payload]
    assert clears and all(p.retain for p in clears)


# --- BMS --------------------------------------------------------------------

def test_bms_node_layout_shares_node_prefix(fake_paho) -> None:
    c = cfg(discovery_node_id=True)
    conn = MqttConnection("b", client_id="mqttpi-node1", base_topic="mqttpi/node1")
    pub = build_publisher(c, connection=conn)
    pub._publish_discovery(4, "uart")
    topics = config_topics(fake_paho.last)
    assert topics and all(t.startswith("homeassistant/") and "/node1/" in t for t in topics)
    assert all(t.split("/")[3].startswith(pub.device_id + "_") for t in topics)
    assert cleared_topics(fake_paho.last)


def test_bms_default_layout_unchanged(fake_paho) -> None:
    conn = MqttConnection("b", client_id="mqttpi-node1", base_topic="mqttpi/node1")
    pub = build_publisher(cfg(), connection=conn)
    pub._publish_discovery(4, "uart")
    topics = config_topics(fake_paho.last)
    assert topics and all(t.count("/") == 3 and t.split("/")[2].startswith(pub.device_id + "_")
                          for t in topics)
