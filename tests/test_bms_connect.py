from __future__ import annotations

from mqttpi.bms.ha_mqtt import BmsMqttPublisher


def test_bms_publisher_connect_is_non_blocking_by_default(fake_paho) -> None:
    pub = BmsMqttPublisher("broker")
    pub.connect()
    names = fake_paho.last.call_names()
    assert "connect_async" in names and "connect" not in names


def test_bms_publisher_blocking_connect_for_one_shot(fake_paho) -> None:
    pub = BmsMqttPublisher("broker")
    pub.connect(blocking=True)
    assert "connect" in fake_paho.last.call_names()


def test_bms_discovery_resent_after_reconnect(fake_paho) -> None:
    pub = BmsMqttPublisher("broker")
    pub.connect()
    pub._discovery_done = True
    fake_paho.last.simulate_connect()
    assert pub._discovery_done is False
