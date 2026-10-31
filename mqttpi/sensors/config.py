"""Parse the ``sensors`` config section.

Accepted shapes (the mapping form is the one documented in ``examples/``)::

    sensors:
      cpu:
        type: cpu_temperature        # aliases: chip, driver
        enabled: true                # default true
        publish: { interval_ms: 30000, retain: true }
        timeout_s: 5                 # default: min(interval, 10 s)
        stale_after_s: 90            # default: 3 x interval (min 10 s)
        readings:
          temperature:
            alias: cpu_temperature
            precision: 1
            ha: { name: "CPU Temperature", device_class: temperature,
                  state_class: measurement, unit_of_measurement: "°C" }

    sensors:                         # list form, each entry has a name
      - { name: cpu, type: cpu_temperature }
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from mqttpi.sensors.registry import available_drivers, get_driver_factory
from mqttpi.sensors.model import EntitySpec, SensorDriver

log = logging.getLogger(__name__)

_ALIAS_RE = re.compile(r"[^A-Za-z0-9_-]")


@dataclass
class SensorConfig:
    name: str
    type: str
    spec: Dict[str, Any]
    interval_s: float
    timeout_s: float
    stale_after_s: float
    entities: List[EntitySpec]


def sensor_entries(cfg: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    raw = cfg.get("sensors")
    entries: List[Tuple[str, Dict[str, Any]]] = []
    if isinstance(raw, dict):
        for name, spec in raw.items():
            if isinstance(spec, dict):
                entries.append((str(name), spec))
    elif isinstance(raw, list):
        for i, spec in enumerate(raw):
            if isinstance(spec, dict):
                entries.append((str(spec.get("name", f"sensor_{i + 1}")), spec))
    return [(n, s) for n, s in entries if s.get("enabled", True)]


def sensor_type(spec: Mapping[str, Any]) -> Optional[str]:
    for key in ("type", "driver", "chip"):
        if spec.get(key):
            return str(spec[key])
    return None


def sensors_configured(cfg: Dict[str, Any]) -> bool:
    """True when at least one enabled sensor has a registered driver."""
    known = set(available_drivers())
    return any((sensor_type(s) or "").lower() in known for _, s in sensor_entries(cfg))


def parse_sensors(cfg: Dict[str, Any]) -> List[Tuple[SensorConfig, SensorDriver]]:
    """Build (config, driver) pairs. Sensors whose ``type`` has no driver yet
    are skipped with a warning, so config contracts documented ahead of their
    drivers keep loading."""
    out: List[Tuple[SensorConfig, SensorDriver]] = []
    aliases: Dict[str, str] = {}
    for name, spec in sensor_entries(cfg):
        type_name = sensor_type(spec)
        if not type_name:
            raise ValueError(f"sensors.{name}: missing 'type'")
        try:
            factory = get_driver_factory(type_name)
        except KeyError:
            log.warning("sensors.%s: no driver for type %r yet — skipped (available: %s)",
                        name, type_name, ", ".join(available_drivers()))
            continue
        driver = factory(spec)
        sc = _sensor_config(name, type_name, spec, driver)
        for e in sc.entities:
            if e.alias in aliases:
                raise ValueError(f"sensors.{name}: alias {e.alias!r} already used by sensors.{aliases[e.alias]}")
            aliases[e.alias] = name
        out.append((sc, driver))
    return out


def _sensor_config(name: str, type_name: str, spec: Dict[str, Any], driver: SensorDriver) -> SensorConfig:
    publish = spec.get("publish") or {}
    interval_s = float(publish.get("interval_ms", spec.get("interval_ms", 30000))) / 1000.0
    if interval_s <= 0:
        raise ValueError(f"sensors.{name}: publish.interval_ms must be > 0")
    timeout_s = float(spec.get("timeout_s", min(interval_s, 10.0)))
    stale_after_s = float(spec.get("stale_after_s", max(3 * interval_s, 10.0)))
    retain = bool(publish.get("retain", True))

    readings = spec.get("readings")
    defaults: Dict[str, Dict[str, Any]] = dict(getattr(driver, "default_readings", {}) or {})
    if not readings:
        readings = {key: {} for key in defaults}
    if not readings:
        raise ValueError(f"sensors.{name}: no readings configured and driver {type_name!r} has no defaults")

    entities: List[EntitySpec] = []
    for key, rcfg in readings.items():
        rcfg = rcfg or {}
        base = defaults.get(key, {})
        ha = {**base, **(rcfg.get("ha") or {})}
        alias = _ALIAS_RE.sub("_", str(rcfg.get("alias", f"{name}_{key}")))
        precision = rcfg.get("precision", ha.pop("precision", None))
        entities.append(
            EntitySpec(
                sensor=name,
                key=str(key),
                alias=alias,
                name=str(ha.pop("name", alias.replace("_", " ").title())),
                unit=ha.pop("unit_of_measurement", None),
                device_class=ha.pop("device_class", None),
                state_class=ha.pop("state_class", "measurement"),
                icon=ha.pop("icon", None),
                precision=int(precision) if precision is not None else None,
                retain=retain,
                extra=ha,
            )
        )
    return SensorConfig(name, type_name, spec, interval_s, timeout_s, stale_after_s, entities)
