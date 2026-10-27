"""I2C climate sensors: Bosch BME280 (temperature, humidity, pressure; BMP280
without humidity) and Sensirion SHT3x / SHT4x (temperature, humidity)."""

from __future__ import annotations

import struct
import time
from typing import Any, Callable, Dict, Optional, Union

from mqttpi.sensors.i2c import I2cBus, open_bus, parse_address
from mqttpi.sensors.model import Reading

_TEMP = {"unit_of_measurement": "°C", "device_class": "temperature", "state_class": "measurement", "precision": 1}
_HUM = {"unit_of_measurement": "%", "device_class": "humidity", "state_class": "measurement", "precision": 1}
_PRES = {"unit_of_measurement": "hPa", "device_class": "atmospheric_pressure",
         "state_class": "measurement", "precision": 1}

Sleep = Callable[[float], None]


BusRef = Union[I2cBus, int]


def _bus_from(spec: Dict[str, Any]) -> int:
    return int(spec.get("bus", 1))


class _I2cDevice:
    """Holds an ``I2cBus`` or a bus number opened lazily on first read, so a
    missing ``smbus2`` or ``/dev/i2c-N`` marks the sensor unavailable instead
    of stopping the daemon."""

    def __init__(self, bus: BusRef, address: int) -> None:
        self._bus_ref, self.address = bus, address

    @property
    def bus(self) -> I2cBus:
        if isinstance(self._bus_ref, int):
            self._bus_ref = open_bus(self._bus_ref)
        return self._bus_ref


# --------------------------------------------------------------------- BME280
class Bme280Driver(_I2cDevice):
    CHIP_ID_BME280 = 0x60
    CHIP_ID_BMP280 = 0x58
    default_readings = {"temperature": _TEMP, "humidity": _HUM, "pressure": _PRES}

    def __init__(self, bus: BusRef = 1, address: int = 0x76, sleep: Sleep = time.sleep) -> None:
        super().__init__(bus, address)
        self._sleep = sleep
        self._cal: Optional[Dict[str, int]] = None
        self.has_humidity = True

    @classmethod
    def from_config(cls, spec: Dict[str, Any]) -> "Bme280Driver":
        return cls(_bus_from(spec), parse_address(spec.get("address"), 0x76))

    def _reg(self, reg: int, n: int) -> bytes:
        return self.bus.write_read(self.address, [reg], n)

    def _load_calibration(self) -> Dict[str, int]:
        chip = self._reg(0xD0, 1)[0]
        if chip not in (self.CHIP_ID_BME280, self.CHIP_ID_BMP280):
            raise IOError(f"BME280 @0x{self.address:02x}: unexpected chip id 0x{chip:02x}")
        self.has_humidity = chip == self.CHIP_ID_BME280
        tp = struct.unpack("<HhhHhhhhhhhh", self._reg(0x88, 24))
        cal = dict(zip(("T1", "T2", "T3", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"), tp))
        if self.has_humidity:
            cal["H1"] = self._reg(0xA1, 1)[0]
            h = self._reg(0xE1, 7)
            cal["H2"] = struct.unpack("<h", h[0:2])[0]
            cal["H3"] = h[2]
            cal["H4"] = _s8(h[3]) * 16 | (h[4] & 0x0F)
            cal["H5"] = _s8(h[5]) * 16 | (h[4] >> 4)
            cal["H6"] = _s8(h[6])
        return cal

    def read(self) -> Reading:
        if self._cal is None:
            self._cal = self._load_calibration()
        # Forced mode, x1 oversampling on every channel: one conversion per read.
        if self.has_humidity:
            self.bus.write(self.address, [0xF2, 0x01])
        self.bus.write(self.address, [0xF4, 0x25])
        for _ in range(20):
            self._sleep(0.005)
            if not self._reg(0xF3, 1)[0] & 0x08:
                break
        else:
            raise IOError(f"BME280 @0x{self.address:02x}: conversion timed out")
        d = self._reg(0xF7, 8)
        adc_p = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4)
        adc_t = (d[3] << 12) | (d[4] << 4) | (d[5] >> 4)
        adc_h = (d[6] << 8) | d[7]
        t_c, t_fine = bme280_temperature(self._cal, adc_t)
        values: Dict[str, Optional[float]] = {
            "temperature": t_c,
            "pressure": bme280_pressure(self._cal, adc_p, t_fine) / 100.0,
        }
        if self.has_humidity:
            values["humidity"] = bme280_humidity(self._cal, adc_h, t_fine)
        return Reading(values)


def _s8(b: int) -> int:
    return b - 256 if b > 127 else b


def bme280_temperature(c: Dict[str, int], adc_t: int):
    """Datasheet floating-point compensation. Returns (°C, t_fine)."""
    v1 = (adc_t / 16384.0 - c["T1"] / 1024.0) * c["T2"]
    v2 = ((adc_t / 131072.0 - c["T1"] / 8192.0) ** 2) * c["T3"]
    t_fine = v1 + v2
    return t_fine / 5120.0, t_fine


def bme280_pressure(c: Dict[str, int], adc_p: int, t_fine: float) -> float:
    """Pascals."""
    v1 = t_fine / 2.0 - 64000.0
    v2 = v1 * v1 * c["P6"] / 32768.0
    v2 = v2 + v1 * c["P5"] * 2.0
    v2 = v2 / 4.0 + c["P4"] * 65536.0
    v1 = (c["P3"] * v1 * v1 / 524288.0 + c["P2"] * v1) / 524288.0
    v1 = (1.0 + v1 / 32768.0) * c["P1"]
    if v1 == 0:
        raise IOError("BME280: invalid pressure calibration")
    p = 1048576.0 - adc_p
    p = (p - v2 / 4096.0) * 6250.0 / v1
    v1 = c["P9"] * p * p / 2147483648.0
    v2 = p * c["P8"] / 32768.0
    return p + (v1 + v2 + c["P7"]) / 16.0


def bme280_humidity(c: Dict[str, int], adc_h: int, t_fine: float) -> float:
    """%RH, clamped to 0..100."""
    h = t_fine - 76800.0
    h = (adc_h - (c["H4"] * 64.0 + c["H5"] / 16384.0 * h)) * (
        c["H2"] / 65536.0 * (1.0 + c["H6"] / 67108864.0 * h * (1.0 + c["H3"] / 67108864.0 * h))
    )
    h = h * (1.0 - c["H1"] * h / 524288.0)
    return max(0.0, min(100.0, h))


# --------------------------------------------------------------------- SHT3x / SHT4x
def sensirion_crc8(data: bytes) -> int:
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def _sensirion_words(raw: bytes):
    if len(raw) != 6:
        raise IOError(f"short read ({len(raw)} bytes)")
    for i in (0, 3):
        if sensirion_crc8(raw[i:i + 2]) != raw[i + 2]:
            raise IOError("CRC mismatch")
    return (raw[0] << 8) | raw[1], (raw[3] << 8) | raw[4]


class Sht3xDriver(_I2cDevice):
    """SHT30/31/35: single shot, high repeatability, no clock stretching."""

    COMMAND = (0x24, 0x00)
    WAIT_S = 0.016
    default_readings = {"temperature": _TEMP, "humidity": _HUM}

    def __init__(self, bus: BusRef = 1, address: int = 0x44, sleep: Sleep = time.sleep) -> None:
        super().__init__(bus, address)
        self._sleep = sleep

    @classmethod
    def from_config(cls, spec: Dict[str, Any]):
        return cls(_bus_from(spec), parse_address(spec.get("address"), 0x44))

    def _convert(self, raw_t: int, raw_h: int) -> Dict[str, Optional[float]]:
        return {"temperature": -45.0 + 175.0 * raw_t / 65535.0,
                "humidity": max(0.0, min(100.0, 100.0 * raw_h / 65535.0))}

    def read(self) -> Reading:
        self.bus.write(self.address, list(self.COMMAND))
        self._sleep(self.WAIT_S)
        try:
            raw_t, raw_h = _sensirion_words(self.bus.read(self.address, 6))
        except IOError as exc:
            raise IOError(f"{type(self).__name__} @0x{self.address:02x}: {exc}") from None
        return Reading(self._convert(raw_t, raw_h))


class Sht4xDriver(Sht3xDriver):
    """SHT40/41/45: high-precision measurement (0xFD)."""

    COMMAND = (0xFD,)
    WAIT_S = 0.010

    def _convert(self, raw_t: int, raw_h: int) -> Dict[str, Optional[float]]:
        return {"temperature": -45.0 + 175.0 * raw_t / 65535.0,
                "humidity": max(0.0, min(100.0, -6.0 + 125.0 * raw_h / 65535.0))}
