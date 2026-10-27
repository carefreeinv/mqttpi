"""The linear-actuator example script enforces its interlock over a real broker."""

from __future__ import annotations

import os
import subprocess
import sys

import paho.mqtt.client as paho
import pytest
import yaml

from tests.integration.conftest import REPO_ROOT, Watcher

pytestmark = pytest.mark.integration


def test_example_interlock_rejects_second_direction(tmp_path, broker) -> None:
    cfg = yaml.safe_load((REPO_ROOT / "examples" / "linear-actuator.yaml").read_text())
    cfg["mqtt"].update(host="127.0.0.1", port=broker.port, keepalive=5)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    base = cfg["mqtt"]["base_topic"]

    log = open(tmp_path / "daemon.log", "ab")
    proc = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "examples" / "linear_actuator_interlock.py"),
         "-c", str(cfg_path), "-s", str(tmp_path / "none.yaml"), "--mock-gpio", "-v"],
        cwd=str(tmp_path), env=dict(os.environ), stdout=log, stderr=log,
    )
    watcher = Watcher(broker.port, f"{base}/#")
    pub = paho.Client(paho.CallbackAPIVersion.VERSION2, client_id="itest-pub")
    pub.connect("127.0.0.1", broker.port)
    pub.loop_start()
    try:
        assert watcher.wait_for(f"{base}/status", "online", timeout=20), (tmp_path / "daemon.log").read_text()
        assert watcher.wait_for(f"{base}/gpio/actuator_retract/state", "OFF")

        pub.publish(f"{base}/gpio/actuator_extend/set", "ON", qos=1).wait_for_publish(5)
        assert watcher.wait_for(f"{base}/gpio/actuator_extend/state", "ON")

        mark = watcher.count()
        pub.publish(f"{base}/gpio/actuator_retract/set", "ON", qos=1).wait_for_publish(5)
        # The true state (OFF) is re-published; ON must never appear.
        assert watcher.wait_for(f"{base}/gpio/actuator_retract/state", "OFF", after=mark)
        assert not watcher.wait_for(f"{base}/gpio/actuator_retract/state", "ON", timeout=1, after=mark)

        pub.publish(f"{base}/gpio/actuator_extend/set", "OFF", qos=1).wait_for_publish(5)
        assert watcher.wait_for(f"{base}/gpio/actuator_extend/state", "OFF", after=mark)
        pub.publish(f"{base}/gpio/actuator_retract/set", "ON", qos=1).wait_for_publish(5)
        assert watcher.wait_for(f"{base}/gpio/actuator_retract/state", "ON", after=mark)

        assert "rejected" in (tmp_path / "daemon.log").read_text()
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        pub.loop_stop()
        pub.disconnect()
        watcher.close()
