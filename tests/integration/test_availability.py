"""Abrupt kill → broker publishes the retained Last Will ``offline``."""

from __future__ import annotations

import signal

import pytest

from tests.integration.conftest import Watcher, retained, start_daemon, write_config

pytestmark = pytest.mark.integration

STATUS = "mqttpi/itest/status"


def test_kill_9_leaves_retained_offline_then_restart_online(broker, tmp_path) -> None:
    config = write_config(tmp_path, broker.port)
    watcher = Watcher(broker.port, "mqttpi/itest/#")
    proc = start_daemon(config)
    try:
        assert watcher.wait_for(STATUS, "online"), (tmp_path / "daemon.log").read_text()
        assert retained(broker.port, STATUS) == "online"

        mark = watcher.count()
        proc.send_signal(signal.SIGKILL)
        proc.wait(timeout=5)
        assert watcher.wait_for(STATUS, "offline", timeout=20, after=mark)
        assert retained(broker.port, STATUS) == "offline"

        mark = watcher.count()
        proc = start_daemon(config)
        assert watcher.wait_for(STATUS, "online", after=mark)
        assert retained(broker.port, STATUS) == "online"
    finally:
        proc.kill()
        proc.wait(timeout=5)
        watcher.close()


def test_clean_stop_publishes_offline(broker, tmp_path) -> None:
    config = write_config(tmp_path, broker.port)
    watcher = Watcher(broker.port, "mqttpi/itest/#")
    proc = start_daemon(config)
    try:
        assert watcher.wait_for(STATUS, "online"), (tmp_path / "daemon.log").read_text()
        mark = watcher.count()
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=10) == 0
        assert watcher.wait_for(STATUS, "offline", after=mark)
        assert retained(broker.port, STATUS) == "offline"
    finally:
        if proc.poll() is None:
            proc.kill()
        watcher.close()
