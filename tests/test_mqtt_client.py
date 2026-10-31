from __future__ import annotations

from mqttpi.mqtt.client import MqttConnection, availability_topic_for


def test_availability_topic_for_strips_trailing_slash() -> None:
    assert availability_topic_for("mqttpi/node/") == "mqttpi/node/status"


def test_will_registered_before_connect(fake_paho) -> None:
    conn = MqttConnection("broker", qos=1, base_topic="mqttpi/node1")
    conn.connect()
    client = fake_paho.last
    names = client.call_names()
    assert names.index("will_set") < names.index("connect_async")
    assert client.will is not None
    assert client.will.topic == "mqttpi/node1/status"
    assert client.will.payload == "offline"
    assert client.will.qos == 1
    assert client.will.retain is True


def test_will_uses_configured_qos_and_payloads(fake_paho) -> None:
    conn = MqttConnection(
        "broker",
        qos=0,
        availability_topic="x/avail",
        payload_available="up",
        payload_not_available="down",
    )
    conn.connect()
    client = fake_paho.last
    assert (client.will.topic, client.will.payload, client.will.qos) == ("x/avail", "down", 0)
    client.simulate_connect()
    assert client.last_payload("x/avail") == "up"


def test_will_can_be_disabled(fake_paho) -> None:
    conn = MqttConnection("broker", base_topic="mqttpi/node1", will=False)
    conn.connect()
    assert "will_set" not in fake_paho.last.call_names()


def test_no_will_without_topic(fake_paho) -> None:
    conn = MqttConnection("broker")
    conn.connect()
    assert "will_set" not in fake_paho.last.call_names()
    fake_paho.last.simulate_connect()
    assert fake_paho.last.published == []


def test_online_published_on_every_connect(fake_paho) -> None:
    conn = MqttConnection("broker", base_topic="mqttpi/node1")
    conn.connect()
    client = fake_paho.last
    assert client.published_to("mqttpi/node1/status") == []
    client.simulate_connect()
    client.simulate_disconnect()
    client.simulate_connect()
    online = client.published_to("mqttpi/node1/status")
    assert [p.payload for p in online] == ["online", "online"]
    assert all(p.retain for p in online)


def test_failed_connect_does_not_announce_online(fake_paho) -> None:
    conn = MqttConnection("broker", base_topic="mqttpi/node1")
    conn.connect()
    fake_paho.last.simulate_connect(rc=5)
    assert fake_paho.last.published == []
    assert conn.is_connected is False


def test_connect_callbacks_run_after_online(fake_paho) -> None:
    conn = MqttConnection("broker", base_topic="b")
    seen = []
    conn.add_connect_callback(lambda: seen.append(len(fake_paho.last.published)))
    conn.connect()
    fake_paho.last.simulate_connect()
    assert seen == [1]  # online already queued
    assert conn.is_connected


def test_connect_callback_exception_is_contained(fake_paho) -> None:
    conn = MqttConnection("broker", base_topic="b")

    def boom() -> None:
        raise RuntimeError("boom")

    ran = []
    conn.add_connect_callback(boom)
    conn.add_connect_callback(lambda: ran.append(True))
    conn.connect()
    fake_paho.last.simulate_connect()
    assert ran == [True]


def test_publish_availability_offline_is_retained(fake_paho) -> None:
    conn = MqttConnection("broker", base_topic="b", retain=False)
    conn.publish_availability(online=False)
    msg = fake_paho.last.published[-1]
    assert (msg.topic, msg.payload, msg.retain) == ("b/status", "offline", True)


def test_publish_availability_legacy_signature(fake_paho) -> None:
    conn = MqttConnection("broker")
    conn.publish_availability("legacy/base", True)
    assert fake_paho.last.last_payload("legacy/base/status") == "online"


def test_keepalive_passed_to_connect(fake_paho) -> None:
    MqttConnection("broker", base_topic="b", keepalive=15).connect()
    name, _args, kwargs = [c for c in fake_paho.last.calls if c[0] == "connect_async"][0]
    assert kwargs["keepalive"] == 15
