from __future__ import annotations

import re
from pathlib import Path

import pytest

import mqttpi

ROOT = Path(__file__).resolve().parents[1]
tomllib = pytest.importorskip("tomllib")  # Python 3.11+


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


def _norm(req: str) -> str:
    return re.sub(r"\s+", "", req.replace("'", '"'))


def test_runtime_dependencies_match_requirements_txt() -> None:
    reqs = [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert sorted(map(_norm, _pyproject()["project"]["dependencies"])) == sorted(map(_norm, reqs))


def test_console_scripts_and_dynamic_version() -> None:
    proj = _pyproject()
    assert proj["project"]["scripts"] == {
        "mqttpi": "mqttpi.daemon:main",
        "mqttpi-bms": "mqttpi.bms.bridge:main",
    }
    assert "version" in proj["project"]["dynamic"]
    assert proj["tool"]["setuptools"]["dynamic"]["version"] == {"attr": "mqttpi.__version__"}
    assert re.fullmatch(r"\d+\.\d+\.\d+", mqttpi.__version__)
