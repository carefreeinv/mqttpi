from __future__ import annotations

import json

from mqttpi.bms.bridge import build_publisher
from mqttpi.bms.ha_mqtt import BmsMqttPublisher
from mqttpi.mqtt.client import MqttConnection

CFG = {"device": {"id": "node1"}, "mqtt": {"host": "broker"}, "bms": {"enabled": True}}


def _discovery_payloads(client):
    return [json.loads(p.payload) for p in client.published
            if p.topic.startswith("homeassistant/") and p.payload]


def test_bms_publisher_connect_is_non_blocking_by_default(fake_paho) -> None:
    pub = BmsMqttPublisher("broker")
    pub.connect()
    names = fake_paho.last.call_names()
    assert "connect_async" in names and "connect" not in names


def test_bms_publisher_blocking_connect_waits_for_broker(fake_paho) -> None:
    pub = BmsMqttPublisher("broker")
    import threading
    threading.Timer(0.1, fake_paho.last.simulate_connect).start()
    pub.connect(blocking=True, timeout=5)
    assert pub.connection.is_connected


def test_bms_publisher_blocking_connect_raises_when_unreachable(fake_paho) -> None:
    pub = BmsMqttPublisher("broker")
    try:
        pub.connect(blocking=True, timeout=0.2)
    except RuntimeError as exc:
        assert "not reachable" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")


def test_bms_discovery_resent_after_reconnect(fake_paho) -> None:
    pub = BmsMqttPublisher("broker")
    pub.connect()
    pub._discovery_done = True
    fake_paho.last.simulate_connect()
    assert pub._discovery_done is False


def test_shared_mode_uses_the_daemon_connection(fake_paho) -> None:
    conn = MqttConnection("broker", client_id="mqttpi-node1", base_topic="mqttpi/node1")
    assert len(fake_paho.instances) == 1
    pub = build_publisher(CFG, connection=conn)
    assert len(fake_paho.instances) == 1, "BMS must not open a second MQTT client"
    assert pub.shared
    assert pub.status_topic == "mqttpi/node1/bms/status"
    pub.connect()
    pub.disconnect()  # no-op: the daemon owns the connection
    assert "disconnect" not in fake_paho.last.call_names()


def test_shared_mode_offline_does_not_touch_node_status(fake_paho) -> None:
    conn = MqttConnection("broker", client_id="mqttpi-node1", base_topic="mqttpi/node1")
    pub = build_publisher(CFG, connection=conn)
    pub.publish_offline()
    client = fake_paho.last
    assert client.last_payload("mqttpi/node1/bms/status") == "offline"
    assert client.published_to("mqttpi/node1/status") == []


def test_shared_mode_discovery_requires_node_and_bms_online(fake_paho) -> None:
    conn = MqttConnection("broker", client_id="mqttpi-node1", base_topic="mqttpi/node1")
    pub = build_publisher(CFG, connection=conn)
    pub._publish_discovery(4, "uart")
    payloads = _discovery_payloads(fake_paho.last)
    assert payloads
    for p in payloads:
        assert p["availability_mode"] == "all"
        assert [a["topic"] for a in p["availability"]] == [
            "mqttpi/node1/status", "mqttpi/node1/bms/status"]
        assert "availability_topic" not in p


def test_standalone_mode_owns_connection_with_distinct_client_id(fake_paho) -> None:
    pub = build_publisher(CFG)
    assert not pub.shared
    assert fake_paho.last.client_id == "mqttpi-node1-bms"
    assert pub.status_topic == "mqttpi/node1/status"
    pub.connect()
    assert fake_paho.last.will.topic == "mqttpi/node1/status"
    pub._publish_discovery(4, "uart")
    for p in _discovery_payloads(fake_paho.last):
        assert p["availability_topic"] == "mqttpi/node1/status"


def test_standalone_client_id_override(fake_paho) -> None:
    build_publisher({**CFG, "bms": {"enabled": True, "client_id": "my-bms"}})
    assert fake_paho.last.client_id == "my-bms"


def test_discovery_payloads_unchanged_between_modes_except_availability(fake_paho) -> None:
    """Snapshot guard: unique ids, topics, and entities match in both modes."""
    standalone = build_publisher(CFG)
    standalone._publish_discovery(4, "uart")
    a = {p.topic: json.loads(p.payload) for p in fake_paho.last.published
         if p.topic.startswith("homeassistant/")}
    conn = MqttConnection("broker", client_id="mqttpi-node1", base_topic="mqttpi/node1")
    shared = build_publisher(CFG, connection=conn)
    shared._publish_discovery(4, "uart")
    b = {p.topic: json.loads(p.payload) for p in fake_paho.last.published
         if p.topic.startswith("homeassistant/")}
    assert a.keys() == b.keys() and a
    strip = ("availability", "availability_topic", "availability_mode")
    for topic in a:
        assert {k: v for k, v in a[topic].items() if k not in strip} == \
               {k: v for k, v in b[topic].items() if k not in strip}
