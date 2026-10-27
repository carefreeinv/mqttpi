"""Home Assistant discovery payload snapshots (GPIO switch / binary_sensor, BMS).

Snapshots live in tests/snapshots/. After an intentional payload change, run
``MQTTPI_UPDATE_SNAPSHOTS=1 pytest tests/test_discovery.py`` and review the diff.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from mqttpi.bms.bridge import build_publisher
from mqttpi.gpio.manager import GpioManager
from mqttpi.mqtt.client import MqttConnection
from mqttpi.mqtt.factory import build_mqtt

SNAPSHOTS = Path(__file__).parent / "snapshots"

CFG = {
    "device": {"id": "node1", "board": "pi4", "ha": {"name": "Test Node"}},
    "mqtt": {"host": "b", "base_topic": "mqttpi/node1", "homeassistant": {"discovery": True}},
    "pins": [
        {"pin": 17, "alias": "relay_1", "direction": "output",
         "ha": {"name": "Relay 1", "icon": "mdi:power-socket"}},
        {"pin": 27, "alias": "door", "direction": "input", "pull": "up",
         "ha": {"name": "Door", "device_class": "door"}},
    ],
    "bms": {"enabled": True, "port": "/dev/ttyUSB0", "ha": {"name": "Pack", "device_id": "pack1"}},
}


def collect(client) -> dict:
    return {p.topic: json.loads(p.payload) for p in client.published
            if p.topic.startswith("homeassistant/") and p.payload}


def check(name: str, payloads: dict) -> None:
    path = SNAPSHOTS / f"{name}.json"
    text = json.dumps(payloads, indent=2, sort_keys=True) + "\n"
    if os.environ.get("MQTTPI_UPDATE_SNAPSHOTS") or not path.exists():
        SNAPSHOTS.mkdir(exist_ok=True)
        path.write_text(text)
    assert json.loads(path.read_text()) == json.loads(text), (
        f"discovery payloads changed; if intended, regenerate {path.name} "
        "with MQTTPI_UPDATE_SNAPSHOTS=1 and review the diff")


def test_gpio_discovery_snapshot(fake_paho) -> None:
    conn = build_mqtt(CFG)
    mgr = GpioManager(CFG, conn, mock_gpio=True)
    mgr.publisher.publish_discovery(mgr.pins)
    payloads = collect(fake_paho.last)
    assert set(payloads) == {"homeassistant/switch/node1_relay_1/config",
                             "homeassistant/binary_sensor/node1_door/config"}
    check("gpio_discovery", payloads)


def test_bms_discovery_snapshot_shared(fake_paho) -> None:
    conn = MqttConnection("b", client_id="mqttpi-node1", base_topic="mqttpi/node1")
    pub = build_publisher(CFG, connection=conn)
    pub._publish_discovery(4, "uart")
    payloads = collect(fake_paho.last)
    assert payloads
    check("bms_discovery_shared_4cells", payloads)


def test_bms_discovery_snapshot_standalone(fake_paho) -> None:
    pub = build_publisher(CFG)
    pub._publish_discovery(4, "uart")
    check("bms_discovery_standalone_4cells", collect(fake_paho.last))
