"""Config loading: YAML + secrets deep-merge."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mqttpi.config import _deep_merge, load_config


def write(path: Path, data) -> Path:
    path.write_text(yaml.safe_dump(data) if not isinstance(data, str) else data)
    return path


def test_load_without_secrets(tmp_path) -> None:
    cfg = load_config(write(tmp_path / "c.yaml", {"mqtt": {"host": "h"}}))
    assert cfg == {"mqtt": {"host": "h"}}


def test_empty_config_is_empty_dict(tmp_path) -> None:
    assert load_config(write(tmp_path / "c.yaml", "")) == {}


def test_missing_secrets_file_is_ignored(tmp_path) -> None:
    cfg = load_config(write(tmp_path / "c.yaml", {"a": 1}), tmp_path / "nope.yaml")
    assert cfg == {"a": 1}


def test_empty_secrets_file_is_ignored(tmp_path) -> None:
    cfg = load_config(write(tmp_path / "c.yaml", {"a": 1}), write(tmp_path / "s.yaml", ""))
    assert cfg == {"a": 1}


def test_secrets_deep_merge(tmp_path) -> None:
    cfg = load_config(
        write(tmp_path / "c.yaml", {"mqtt": {"host": "h", "username": "", "homeassistant": {"discovery": True}},
                                    "pins": [{"pin": 17, "alias": "a"}]}),
        write(tmp_path / "s.yaml", {"mqtt": {"username": "u", "password": "p"}}),
    )
    assert cfg["mqtt"] == {"host": "h", "username": "u", "password": "p",
                           "homeassistant": {"discovery": True}}
    assert cfg["pins"] == [{"pin": 17, "alias": "a"}]


def test_deep_merge_rules() -> None:
    base = {"a": {"b": 1, "c": {"d": 2}}, "l": [1, 2], "s": "x"}
    over = {"a": {"c": {"e": 3}}, "l": [9], "s": {"now": "dict"}}
    merged = _deep_merge(base, over)
    assert merged == {"a": {"b": 1, "c": {"d": 2, "e": 3}}, "l": [9], "s": {"now": "dict"}}
    assert base == {"a": {"b": 1, "c": {"d": 2}}, "l": [1, 2], "s": "x"}  # not mutated


def test_invalid_yaml_raises(tmp_path) -> None:
    with pytest.raises(yaml.YAMLError):
        load_config(write(tmp_path / "c.yaml", "mqtt: [unclosed"))


def test_missing_config_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.yaml")


def test_repo_example_and_secrets_template_merge() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "config.example.yaml", root / "secrets.example.yaml")
    assert cfg["mqtt"]["host"]
    assert "device" in cfg
