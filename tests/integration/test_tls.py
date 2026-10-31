"""TLS to a real broker: verified CA connects, wrong CA is refused and logged."""

from __future__ import annotations

import time

import pytest

from tests.certs import make_ca, make_leaf
from tests.integration.conftest import Broker, Watcher, start_daemon, write_config

pytestmark = pytest.mark.integration

STATUS = "mqttpi/itest/status"


@pytest.fixture
def tls_broker(tmp_path):
    certs = tmp_path / "certs"
    ca = make_ca(certs, "test-ca")
    server = make_leaf(certs, ca, "server")
    broker = Broker(tmp_path, tls=server)
    broker.start()
    try:
        yield broker, ca, certs
    finally:
        broker.stop()


def test_daemon_connects_with_test_ca(tmp_path, tls_broker) -> None:
    broker, ca, _ = tls_broker
    config = write_config(tmp_path, broker.port, {"tls": {"ca_certs": str(ca["crt"])}})
    proc = start_daemon(config)
    watcher = Watcher(broker.port, "#", ca_certs=ca["crt"])
    try:
        assert watcher.wait_for(STATUS, "online", timeout=20), (tmp_path / "daemon.log").read_text()
        log = (tmp_path / "daemon.log").read_text()
        assert "over TLS (CA " in log
        assert "BEGIN" not in log  # no key/cert material in logs
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        watcher.close()


def test_daemon_refuses_wrong_ca(tmp_path, tls_broker) -> None:
    broker, ca, certs = tls_broker
    other = make_ca(certs / "other", "other-ca")
    config = write_config(
        tmp_path, broker.port,
        {"tls": {"ca_certs": str(other["crt"])}, "reconnect_min_s": 1, "reconnect_max_s": 2},
    )
    proc = start_daemon(config)
    watcher = Watcher(broker.port, "#", ca_certs=ca["crt"])
    try:
        assert not watcher.wait_for(STATUS, "online", timeout=6)
        assert proc.poll() is None  # keeps running and retrying
        deadline = time.monotonic() + 5
        log = ""
        while time.monotonic() < deadline and "TLS handshake failed" not in log:
            log = (tmp_path / "daemon.log").read_text()
            time.sleep(0.2)
        assert "TLS handshake failed" in log and "CERTIFICATE_VERIFY_FAILED" in log, log
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        watcher.close()
