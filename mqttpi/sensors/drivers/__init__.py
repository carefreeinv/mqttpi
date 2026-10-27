"""Built-in sensor drivers (hardware drivers register here as they land)."""

from __future__ import annotations


def register_builtin_drivers() -> None:
    from mqttpi.sensors.drivers.cpu_temperature import CpuTemperatureDriver
    from mqttpi.sensors.registry import register_driver

    register_driver("cpu_temperature", CpuTemperatureDriver.from_config, replace=True)
