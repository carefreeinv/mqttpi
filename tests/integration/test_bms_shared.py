"""Unified daemon with BMS enabled: one MQTT client, separate BMS availability."""

from __future__ import annotations

import time

import pytest
import yaml

from tests.integration.conftest import Watcher, retained, start_daemon, write_config

pytestmark = pytest.mark.integration

NODE_STATUS = "mqttpi/itest/status"
BMS_STATUS = "mqttpi/itest/bms/status"


def test_bms_failure_does_not_mark_node_offline(tmp_path, broker) -> None:
    config = write_config(tmp_path, broker.port)
    cfg = yaml.safe_load(config.read_text())
    # A serial port that does not exist: every poll fails.
    cfg["bms"] = {"enabled": True, "port": str(tmp_path / "no-such-tty"),
                  "poll_interval": 1, "retry_delay": 1}
    config.write_text(yaml.safe_dump(cfg))

    watcher = Watcher(broker.port, "#")
    proc = start_daemon(config)
    try:
        log = lambda: (tmp_path / "daemon.log").read_text()  # noqa: E731
        assert watcher.wait_for(NODE_STATUS, "online", timeout=20), log()
        assert watcher.wait_for(BMS_STATUS, "offline", timeout=20), log()
        time.sleep(2.5)  # a couple more failed polls
        assert proc.poll() is None, log()
        assert retained(broker.port, NODE_STATUS) == "online"
        assert retained(broker.port, BMS_STATUS) == "offline"
        assert "-bms" not in log()  # no second (standalone) BMS client
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        watcher.close()
    assert retained(broker.port, NODE_STATUS) == "offline"
