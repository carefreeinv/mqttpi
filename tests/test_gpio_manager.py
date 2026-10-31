"""GpioManager with the mock backend and the fake MQTT client."""

from __future__ import annotations

import time

import pytest

from mqttpi.gpio.manager import GpioManager
from mqttpi.mqtt.factory import build_mqtt


def make_cfg(pins, **mqtt):
    return {"device": {"id": "n", "board": "pi4"},
            "mqtt": {"host": "b", "base_topic": "mqttpi/n", **mqtt}, "pins": pins}


@pytest.fixture
def started(fake_paho):
    managers = []

    def _start(pins, **mqtt):
        cfg = make_cfg(pins, **mqtt)
        conn = build_mqtt(cfg)
        mgr = GpioManager(cfg, conn, mock_gpio=True)
        conn.set_message_handler(mgr.handle_mqtt_message)  # as the daemon does
        conn.connect()
        fake_paho.last.simulate_connect()
        mgr.start()
        managers.append(mgr)
        return mgr, fake_paho.last

    yield _start
    for m in managers:
        m.stop()


def wait_until(pred, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.01)
    return pred()


def test_requires_supported_pins(fake_paho) -> None:
    cfg = make_cfg([{"pin": 18, "alias": "x", "direction": "pwm"}])
    with pytest.raises(ValueError):
        GpioManager(cfg, build_mqtt(cfg), mock_gpio=True)


def test_output_initial_state_and_subscription(started) -> None:
    mgr, client = started([{"pin": 17, "alias": "r1", "initial": True}, {"pin": 22, "alias": "r2"}])
    assert mgr.backend.read(17) is True and mgr.backend.read(22) is False
    assert "mqttpi/n/gpio/r1/set" in [t for t, _q in client.subscriptions]
    assert client.last_payload("mqttpi/n/gpio/r1/state") == "ON"
    assert client.last_payload("mqttpi/n/gpio/r2/state") == "OFF"


def test_mqtt_command_drives_pin_and_echoes_state(started) -> None:
    mgr, client = started([{"pin": 17, "alias": "r1"}])
    client.simulate_message("mqttpi/n/gpio/r1/set", "ON")
    assert mgr.backend.read(17) is True
    assert client.last_payload("mqttpi/n/gpio/r1/state") == "ON"
    client.simulate_message("mqttpi/n/gpio/r1/set", "OFF")
    assert mgr.backend.read(17) is False


def test_unknown_payload_and_alias_are_ignored(started) -> None:
    mgr, client = started([{"pin": 17, "alias": "r1"}])
    before = len(client.published)
    client.simulate_message("mqttpi/n/gpio/r1/set", "maybe")
    client.simulate_message("mqttpi/n/gpio/nope/set", "ON")
    client.simulate_message("other/topic", "ON")
    assert mgr.backend.read(17) is False
    assert len(client.published) == before


def test_custom_payloads(started) -> None:
    mgr, client = started([{"pin": 17, "alias": "r1"}], payload_on="1", payload_off="0")
    client.simulate_message("mqttpi/n/gpio/r1/set", "1")
    assert mgr.backend.read(17) is True
    assert client.last_payload("mqttpi/n/gpio/r1/state") == "1"


def test_inverted_output_is_active_low(started) -> None:
    mgr, client = started([{"pin": 17, "alias": "r1", "invert": True}])
    assert mgr.backend.read(17) is True  # logical OFF → pin HIGH
    client.simulate_message("mqttpi/n/gpio/r1/set", "ON")
    assert mgr.backend.read(17) is False
    assert client.last_payload("mqttpi/n/gpio/r1/state") == "ON"


def test_input_idle_follows_pull_and_invert(started) -> None:
    mgr, client = started([
        {"pin": 27, "alias": "up", "direction": "input", "pull": "up"},
        {"pin": 22, "alias": "up_inv", "direction": "input", "pull": "up", "invert": True},
        {"pin": 23, "alias": "down", "direction": "input", "pull": "down"},
    ])
    assert mgr.states() == {"up": True, "up_inv": False, "down": False}
    assert client.last_payload("mqttpi/n/gpio/up_inv/state") == "OFF"


def test_input_change_is_published(started) -> None:
    mgr, client = started([{"pin": 27, "alias": "door", "direction": "input",
                            "pull": "up", "invert": True, "debounce_ms": 0}])
    mgr.backend.write(27, False)  # pulled low = active
    assert wait_until(lambda: client.last_payload("mqttpi/n/gpio/door/state") == "ON")
    mgr.backend.write(27, True)
    assert wait_until(lambda: client.last_payload("mqttpi/n/gpio/door/state") == "OFF")


def test_input_debounce_suppresses_chatter(started) -> None:
    mgr, client = started([{"pin": 27, "alias": "b", "direction": "input", "pull": "down",
                            "debounce_ms": 300}])
    mgr.backend.write(27, True)
    assert wait_until(lambda: client.last_payload("mqttpi/n/gpio/b/state") == "ON")
    # chatter inside the debounce window is not published
    for v in (False, True, False, True):
        mgr.backend.write(27, v)
        time.sleep(0.03)
    assert [p.payload for p in client.published_to("mqttpi/n/gpio/b/state")] == ["OFF", "ON"]


def test_input_change_settling_inside_debounce_window_is_published(started) -> None:
    mgr, client = started([{"pin": 27, "alias": "b", "direction": "input", "pull": "down",
                            "debounce_ms": 100}])
    mgr.backend.write(27, True)
    assert wait_until(lambda: client.last_payload("mqttpi/n/gpio/b/state") == "ON")
    mgr.backend.write(27, False)  # released 0 ms later and stays released
    assert wait_until(lambda: client.last_payload("mqttpi/n/gpio/b/state") == "OFF", timeout=1.0)


def test_announce_republishes_on_reconnect(started) -> None:
    mgr, client = started([{"pin": 17, "alias": "r1"}])
    n = len(client.published_to("homeassistant/switch/n_r1/config"))
    client.simulate_disconnect()
    client.simulate_connect()
    assert len(client.published_to("homeassistant/switch/n_r1/config")) == n + 1


def test_discovery_can_be_disabled(started) -> None:
    _mgr, client = started([{"pin": 17, "alias": "r1"}], homeassistant={"discovery": False})
    assert not [p for p in client.published if p.topic.startswith("homeassistant/")]
    assert client.last_payload("mqttpi/n/gpio/r1/state") == "OFF"


def test_stop_cleans_up_backend(started) -> None:
    mgr, _client = started([{"pin": 17, "alias": "r1", "initial": True}])
    mgr.stop()
    assert mgr.backend.read(17) is False


def test_glitch_shorter_than_debounce_is_ignored(started) -> None:
    mgr, client = started([{"pin": 27, "alias": "b", "direction": "input", "pull": "down",
                            "debounce_ms": 200}])
    mgr.backend.write(27, True)
    time.sleep(0.06)
    mgr.backend.write(27, False)
    time.sleep(0.3)
    assert [p.payload for p in client.published_to("mqttpi/n/gpio/b/state")] == ["OFF"]

