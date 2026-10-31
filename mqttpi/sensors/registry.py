"""Driver registry keyed by the config ``type`` (alias ``chip`` / ``driver``)."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from mqttpi.sensors.model import SensorDriver

#: factory(spec) -> driver; ``spec`` is the sensor's config mapping.
DriverFactory = Callable[[Dict[str, Any]], SensorDriver]

_REGISTRY: Dict[str, DriverFactory] = {}


def register_driver(type_name: str, factory: DriverFactory, *, replace: bool = False) -> None:
    key = type_name.strip().lower()
    if key in _REGISTRY and not replace:
        raise ValueError(f"Sensor driver {type_name!r} already registered")
    _REGISTRY[key] = factory


def unregister_driver(type_name: str) -> None:
    _REGISTRY.pop(type_name.strip().lower(), None)


def get_driver_factory(type_name: str) -> DriverFactory:
    _load_builtins()
    try:
        return _REGISTRY[type_name.strip().lower()]
    except KeyError:
        raise KeyError(type_name) from None


def available_drivers() -> List[str]:
    _load_builtins()
    return sorted(_REGISTRY)


_BUILTINS_LOADED = False


def _load_builtins() -> None:
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED:
        return
    _BUILTINS_LOADED = True
    from mqttpi.sensors.drivers import register_builtin_drivers

    register_builtin_drivers()
