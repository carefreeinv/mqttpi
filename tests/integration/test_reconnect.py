"""Daemon survives a broker-down boot and a broker restart."""

from __future__ import annotations

import time

import pytest

from tests.integration.conftest import Broker, Watcher, start_daemon, write_config

pytestmark = pytest.mark.integration

STATUS = "mqttpi/itest/status"
DISCOVERY = "homeassistant/switch/itest_relay_1/config"


def test_broker_down_at_boot_then_restart(tmp_path) -> None:
    broker = Broker(tmp_path)  # port reserved, not started
    config = write_config(tmp_path, broker.port, {"reconnect_min_s": 1, "reconnect_max_s": 2})
    proc = start_daemon(config)
    watcher = None
    try:
        time.sleep(4)
        assert proc.poll() is None, "daemon exited while broker was down:\n" + (
            tmp_path / "daemon.log").read_text()

        broker.start()
        watcher = Watcher(broker.port, "#")
        assert watcher.wait_for(STATUS, "online", timeout=20), (tmp_path / "daemon.log").read_text()
        assert watcher.wait_for(DISCOVERY, timeout=10)

        # Broker restart without persistence: retained state is gone and must
        # be re-published by the daemon after it reconnects.
        watcher.close()
        broker.stop()
        time.sleep(2)
        assert proc.poll() is None
        broker.start()
        watcher = Watcher(broker.port, "#")
        assert watcher.wait_for(STATUS, "online", timeout=20), (tmp_path / "daemon.log").read_text()
        assert watcher.wait_for(DISCOVERY, timeout=10)

        log = (tmp_path / "daemon.log").read_text()
        assert log.count("retrying in background") <= 2  # one warning per outage
    finally:
        proc.kill()
        proc.wait(timeout=5)
        if watcher is not None:
            watcher.close()
        broker.stop()
