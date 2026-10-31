from __future__ import annotations

import logging
import ssl

import pytest

from mqttpi.bms.bridge import build_publisher
from mqttpi.config import TlsSettings, mqtt_port, parse_tls
from mqttpi.daemon import build_mqtt
from mqttpi.mqtt.client import MqttConnection


@pytest.fixture
def pem(tmp_path):
    files = {}
    for name in ("ca.crt", "client.crt", "client.key"):
        f = tmp_path / name
        f.write_text("placeholder")
        files[name] = str(f)
    return files


def test_parse_tls_off_and_true() -> None:
    assert parse_tls(None) is None
    assert parse_tls(False) is None
    assert parse_tls(True) == TlsSettings()


def test_parse_tls_mapping(pem) -> None:
    t = parse_tls({"ca_certs": pem["ca.crt"], "certfile": pem["client.crt"],
                   "keyfile": pem["client.key"], "insecure": True})
    assert t == TlsSettings(pem["ca.crt"], pem["client.crt"], pem["client.key"], True)
    assert "hostname check OFF" in t.describe()
    assert parse_tls({}) == TlsSettings()


@pytest.mark.parametrize(
    "value, match",
    [
        ("yes", "true, false, or a mapping"),
        ({"cafile": "x"}, "unknown key"),
        ({"ca_certs": "/nonexistent/ca.crt"}, "file not found"),
        ({"ca_certs": 5}, "file path"),
        ({"insecure": "true"}, "insecure must be"),
    ],
)
def test_parse_tls_errors(value, match) -> None:
    with pytest.raises(ValueError, match=match):
        parse_tls(value)


def test_keyfile_requires_certfile(pem) -> None:
    with pytest.raises(ValueError, match="requires mqtt.tls.certfile"):
        parse_tls({"keyfile": pem["client.key"]})


def test_port_default_follows_tls() -> None:
    assert mqtt_port({}, None) == 1883
    assert mqtt_port({}, TlsSettings()) == 8883
    assert mqtt_port({"port": 1884}, TlsSettings()) == 1884
    assert mqtt_port({"port": 8883}, None) == 8883


def test_connection_applies_tls(fake_paho, pem) -> None:
    tls = TlsSettings(ca_certs=pem["ca.crt"])
    conn = MqttConnection("broker", port=8883, base_topic="mqttpi/x", tls=tls)
    calls = [c for c in fake_paho.last.calls if c[0] == "tls_set"]
    assert calls and calls[0][2]["ca_certs"] == pem["ca.crt"]
    assert calls[0][2]["cert_reqs"] == ssl.CERT_REQUIRED
    assert "tls_insecure_set" not in fake_paho.last.call_names()
    assert conn.transport.startswith("TLS (CA ")


def test_insecure_warns_and_disables_hostname_check(fake_paho, caplog) -> None:
    with caplog.at_level(logging.WARNING):
        MqttConnection("broker", base_topic="mqttpi/x", tls=TlsSettings(insecure=True))
    assert ("tls_insecure_set", (True,), {}) in fake_paho.last.calls
    assert "hostname is NOT verified" in caplog.text


def test_no_tls_by_default(fake_paho) -> None:
    conn = MqttConnection("broker", base_topic="mqttpi/x")
    assert "tls_set" not in fake_paho.last.call_names()
    assert conn.transport == "plain TCP"


def test_build_mqtt_tls_true_uses_8883(fake_paho, caplog) -> None:
    cfg = {"device": {"id": "n"}, "mqtt": {"host": "broker", "tls": True}}
    with caplog.at_level(logging.INFO):
        conn = build_mqtt(cfg)
        conn.connect()
    assert conn.port == 8883
    assert "tls_set" in fake_paho.last.call_names()
    assert "over TLS (system CA store)" in caplog.text


def test_build_mqtt_tls_false_keeps_1883(fake_paho) -> None:
    conn = build_mqtt({"mqtt": {"host": "broker", "tls": False}})
    assert conn.port == 1883 and conn.tls is None


def test_bad_certificate_file_fails_fast(tmp_path) -> None:
    bad = tmp_path / "ca.crt"
    bad.write_text("not a certificate")
    with pytest.raises(ValueError, match="cannot load certificates"):
        MqttConnection("broker", base_topic="mqttpi/x", tls=TlsSettings(ca_certs=str(bad)))


def test_tls_handshake_failure_is_explained(fake_paho, caplog) -> None:
    conn = MqttConnection("broker", base_topic="mqttpi/x", tls=TlsSettings())
    with caplog.at_level(logging.WARNING):
        try:
            raise ssl.SSLError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
        except ssl.SSLError:
            conn._on_connect_fail(fake_paho.last, None)
    assert "TLS handshake failed" in caplog.text and "system clock" in caplog.text


def test_bms_publisher_gets_tls(fake_paho) -> None:
    pub = build_publisher({"device": {"id": "n"}, "mqtt": {"host": "b", "tls": True}})
    assert pub.port == 8883
    assert "tls_set" in fake_paho.last.call_names()
