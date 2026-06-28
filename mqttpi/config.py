"""Load config.yaml and merge secrets.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

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