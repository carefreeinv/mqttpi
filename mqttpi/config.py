"""Load config.yaml and merge secrets.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(
    config_path: Path,
    secrets_path: Path | None = None,
) -> Dict[str, Any]:
    with config_path.open() as f:
        cfg = yaml.safe_load(f) or {}

    if secrets_path and secrets_path.exists():
        with secrets_path.open() as f:
            secrets = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, secrets)

    return cfg

DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_TLS_PORT = 8883
TLS_KEYS = frozenset({"ca_certs", "certfile", "keyfile", "insecure"})


@dataclass(frozen=True)
class TlsSettings:
    """Parsed ``mqtt.tls``. ``ca_certs=None`` means the system CA store."""

    ca_certs: Optional[str] = None
    certfile: Optional[str] = None
    keyfile: Optional[str] = None
    insecure: bool = False

    def describe(self) -> str:
        """Log-safe summary (paths only, never key material)."""
        parts = [f"CA {self.ca_certs}" if self.ca_certs else "system CA store"]
        if self.certfile:
            parts.append(f"client cert {self.certfile}")
        if self.insecure:
            parts.append("hostname check OFF")
        return ", ".join(parts)


def parse_tls(value: Any) -> Optional[TlsSettings]:
    """Parse ``mqtt.tls``: ``false``/missing → None, ``true`` → system CAs,
    or a mapping with ``ca_certs``, ``certfile``, ``keyfile``, ``insecure``.

    Raises ``ValueError`` with a config-path-specific message on bad input,
    including referenced files that do not exist.
    """
    if value is None or value is False:
        return None
    if value is True:
        return TlsSettings()
    if not isinstance(value, dict):
        raise ValueError(f"mqtt.tls must be true, false, or a mapping (got {value!r})")
    unknown = set(value) - TLS_KEYS
    if unknown:
        raise ValueError(
            f"mqtt.tls: unknown key(s) {', '.join(sorted(unknown))}; "
            f"allowed: {', '.join(sorted(TLS_KEYS))}"
        )
    paths: Dict[str, Optional[str]] = {}
    for key in ("ca_certs", "certfile", "keyfile"):
        raw = value.get(key)
        if raw in (None, ""):
            paths[key] = None
            continue
        if not isinstance(raw, str):
            raise ValueError(f"mqtt.tls.{key} must be a file path")
        path = Path(raw).expanduser()
        if not path.is_file():
            raise ValueError(f"mqtt.tls.{key}: file not found: {path}")
        paths[key] = str(path)
    if paths["keyfile"] and not paths["certfile"]:
        raise ValueError("mqtt.tls.keyfile requires mqtt.tls.certfile")
    insecure = value.get("insecure", False)
    if not isinstance(insecure, bool):
        raise ValueError("mqtt.tls.insecure must be true or false")
    return TlsSettings(insecure=insecure, **paths)


def mqtt_port(mqtt_cfg: Dict[str, Any], tls: Optional[TlsSettings]) -> int:
    """``mqtt.port`` if set, else 8883 with TLS and 1883 without."""
    if mqtt_cfg.get("port") not in (None, ""):
        return int(mqtt_cfg["port"])
    return DEFAULT_MQTT_TLS_PORT if tls is not None else DEFAULT_MQTT_PORT
