"""Built-in sensor drivers (hardware drivers register here as they land)."""

from __future__ import annotations


def register_builtin_drivers() -> None:
    from mqttpi.sensors.drivers.cpu_temperature import CpuTemperatureDriver
    from mqttpi.sensors.drivers.ds18b20 import Ds18b20Driver
    from mqttpi.sensors.drivers.i2c_climate import Bme280Driver, Sht3xDriver, Sht4xDriver
    from mqttpi.sensors.registry import register_driver

    register_driver("cpu_temperature", CpuTemperatureDriver.from_config, replace=True)
    register_driver("ds18b20", Ds18b20Driver.from_config, replace=True)
    register_driver("bme280", Bme280Driver.from_config, replace=True)
    register_driver("bmp280", Bme280Driver.from_config, replace=True)
    for name in ("sht3x", "sht30", "sht31", "sht35"):
        register_driver(name, Sht3xDriver.from_config, replace=True)
    for name in ("sht4x", "sht40", "sht41", "sht45"):
        register_driver(name, Sht4xDriver.from_config, replace=True)
