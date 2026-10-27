"""DS18B20 (fake w1 sysfs), BME280 / SHT3x / SHT4x (fake I2C register maps)."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

from mqttpi.config import load_config
from mqttpi.sensors import QUALITY_UNCERTAIN
from mqttpi.sensors.config import parse_sensors, sensors_configured
from mqttpi.sensors.drivers.ds18b20 import Ds18b20Driver, list_probes, parse_w1_slave
from mqttpi.sensors.drivers.i2c_climate import (
    Bme280Driver,
    Sht3xDriver,
    Sht4xDriver,
    bme280_humidity,
    bme280_pressure,
    bme280_temperature,
    sensirion_crc8,
)
from mqttpi.sensors.i2c import I2cBus, open_bus, parse_address, reset_bus_factory, set_bus_factory

ROOT = Path(__file__).resolve().parents[1]
NOSLEEP = lambda s: None  # noqa: E731


# -- DS18B20 ---------------------------------------------------------------

W1_OK = "72 01 4b 46 7f ff 0e 10 57 : crc=57 YES\n72 01 4b 46 7f ff 0e 10 57 t=23125\n"
W1_BADCRC = "72 01 4b 46 7f ff 0e 10 57 : crc=57 NO\n72 01 4b 46 7f ff 0e 10 57 t=23125\n"


def probe(root: Path, addr: str, w1_slave: str = None, temperature: str = None) -> Path:
    d = root / addr
    d.mkdir(parents=True)
    if w1_slave is not None:
        (d / "w1_slave").write_text(w1_slave)
    if temperature is not None:
        (d / "temperature").write_text(temperature)
    return d


def test_parse_w1_slave() -> None:
    assert parse_w1_slave(W1_OK) == 23125
    assert parse_w1_slave(W1_OK.replace("t=23125", "t=-1250")) == -1250
    with pytest.raises(IOError, match="CRC"):
        parse_w1_slave(W1_BADCRC)
    with pytest.raises(IOError):
        parse_w1_slave("")


def test_ds18b20_reads_w1_slave_and_temperature_file(tmp_path) -> None:
    probe(tmp_path, "28-0000000000a1", w1_slave=W1_OK)
    probe(tmp_path, "28-0000000000b2", w1_slave=W1_BADCRC, temperature="-10500\n")
    (tmp_path / "w1_bus_master1").mkdir()
    assert list_probes(str(tmp_path)) == ["28-0000000000a1", "28-0000000000b2"]
    assert Ds18b20Driver("28-0000000000A1", str(tmp_path)).read().values == {"temperature": 23.125}
    # the plain ``temperature`` file wins when present
    assert Ds18b20Driver("28-0000000000b2", str(tmp_path)).read().values == {"temperature": -10.5}


def test_ds18b20_autodetect_single_probe_only(tmp_path) -> None:
    with pytest.raises(IOError, match="w1-gpio"):
        Ds18b20Driver(None, str(tmp_path)).read()
    probe(tmp_path, "28-0000000000a1", w1_slave=W1_OK)
    assert Ds18b20Driver(None, str(tmp_path)).read().values["temperature"] == 23.125
    probe(tmp_path, "28-0000000000b2", w1_slave=W1_OK)
    with pytest.raises(IOError, match="found 2 probes"):
        Ds18b20Driver(None, str(tmp_path)).read()


def test_ds18b20_failures(tmp_path) -> None:
    probe(tmp_path, "28-p", temperature="85000")
    probe(tmp_path, "28-q", temperature="")
    probe(tmp_path, "28-r", temperature="-127000")
    assert Ds18b20Driver("28-p", str(tmp_path)).read().quality == QUALITY_UNCERTAIN
    for addr in ("28-q", "28-r"):
        with pytest.raises(IOError):
            Ds18b20Driver(addr, str(tmp_path)).read()
    with pytest.raises(FileNotFoundError):
        Ds18b20Driver("28-missing", str(tmp_path)).read()  # probe unplugged


def test_ds18b20_from_config(tmp_path) -> None:
    probe(tmp_path, "28-0000000000a1", w1_slave=W1_OK)
    [(sc, drv)] = parse_sensors({"sensors": {"tank": {
        "type": "ds18b20", "address": "28-0000000000a1", "sysfs_root": str(tmp_path)}}})
    assert drv.read().values == {"temperature": 23.125}
    [e] = sc.entities
    assert (e.alias, e.unit, e.device_class, e.precision) == ("tank_temperature", "°C", "temperature", 2)


# -- fake I2C ---------------------------------------------------------------

class FakeI2c:
    """Register-map devices keyed by address. ``write_read`` reads registers;
    raw ``write``/``read`` go to a per-device handler (Sensirion commands)."""

    def __init__(self) -> None:
        self.regs: Dict[int, Dict[int, int]] = {}
        self.raw: Dict[int, bytes] = {}
        self.writes: List[Tuple[int, Tuple[int, ...]]] = []
        self.fail = False

    def write(self, address: int, data) -> None:
        self._check(address)
        self.writes.append((address, tuple(data)))
        if address in self.regs and len(data) >= 2:
            self.regs[address][data[0]] = data[1]

    def read(self, address: int, length: int) -> bytes:
        self._check(address)
        return self.raw[address][:length]

    def write_read(self, address: int, data, length: int) -> bytes:
        self._check(address)
        reg = data[0]
        return bytes(self.regs[address].get(reg + i, 0) for i in range(length))

    def _check(self, address: int) -> None:
        if self.fail or (address not in self.regs and address not in self.raw):
            raise OSError(121, "Remote I/O error")  # what smbus2 raises on NACK


def test_fake_bus_satisfies_protocol() -> None:
    assert isinstance(FakeI2c(), I2cBus)


# Bosch BME280 datasheet worked example (temperature/pressure), plus a typical
# humidity calibration from a production part.
CAL = dict(T1=27504, T2=26435, T3=-1000, P1=36477, P2=-10685, P3=3024, P4=2855, P5=140,
           P6=-7, P7=15500, P8=-14600, P9=6000, H1=75, H2=362, H3=0, H4=324, H5=50, H6=30)
ADC_T, ADC_P, ADC_H = 519888, 415148, 30000


def bme280_regs(chip: int = 0x60) -> Dict[int, int]:
    regs: Dict[int, int] = {0xD0: chip, 0xF3: 0}
    tp = struct.pack("<HhhHhhhhhhhh", *(CAL[k] for k in
                     ("T1", "T2", "T3", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9")))
    for i, b in enumerate(tp):
        regs[0x88 + i] = b
    regs[0xA1] = CAL["H1"]
    h = struct.pack("<hB", CAL["H2"], CAL["H3"]) + bytes([
        (CAL["H4"] >> 4) & 0xFF, (CAL["H4"] & 0x0F) | ((CAL["H5"] & 0x0F) << 4),
        (CAL["H5"] >> 4) & 0xFF, CAL["H6"] & 0xFF])
    for i, b in enumerate(h):
        regs[0xE1 + i] = b
    data = [ADC_P >> 12, (ADC_P >> 4) & 0xFF, (ADC_P & 0x0F) << 4,
            ADC_T >> 12, (ADC_T >> 4) & 0xFF, (ADC_T & 0x0F) << 4, ADC_H >> 8, ADC_H & 0xFF]
    for i, b in enumerate(data):
        regs[0xF7 + i] = b
    return regs


def test_bme280_compensation_matches_datasheet_example() -> None:
    t, t_fine = bme280_temperature(CAL, ADC_T)
    assert t == pytest.approx(25.08, abs=0.01)
    assert bme280_pressure(CAL, ADC_P, t_fine) == pytest.approx(100653.27, abs=0.5)
    h = bme280_humidity(CAL, ADC_H, t_fine)
    assert 0.0 < h < 100.0
    assert bme280_humidity(CAL, ADC_H + 2000, t_fine) > h  # monotonic in the raw value
    assert bme280_humidity(CAL, 0, t_fine) == 0.0  # clamped


def test_bme280_driver_reads_through_bus() -> None:
    bus = FakeI2c()
    bus.regs[0x76] = bme280_regs()
    r = Bme280Driver(bus, 0x76, sleep=NOSLEEP).read()
    t_fine = bme280_temperature(CAL, ADC_T)[1]
    assert r.values["temperature"] == pytest.approx(25.08, abs=0.01)
    assert r.values["pressure"] == pytest.approx(1006.53, abs=0.01)  # hPa
    assert r.values["humidity"] == pytest.approx(bme280_humidity(CAL, ADC_H, t_fine))
    assert (0x76, (0xF2, 0x01)) in bus.writes and (0x76, (0xF4, 0x25)) in bus.writes  # forced mode


def test_bmp280_has_no_humidity_and_bad_chip_id_fails() -> None:
    bus = FakeI2c()
    bus.regs[0x77] = bme280_regs(chip=0x58)
    r = Bme280Driver(bus, 0x77, sleep=NOSLEEP).read()
    assert set(r.values) == {"temperature", "pressure"}
    bus.regs[0x76] = bme280_regs(chip=0x00)
    with pytest.raises(IOError, match="chip id"):
        Bme280Driver(bus, 0x76, sleep=NOSLEEP).read()


def test_bme280_conversion_timeout_and_nack() -> None:
    bus = FakeI2c()
    bus.regs[0x76] = bme280_regs()
    bus.regs[0x76][0xF3] = 0x08  # stuck "measuring"
    with pytest.raises(IOError, match="timed out"):
        Bme280Driver(bus, 0x76, sleep=NOSLEEP).read()
    with pytest.raises(OSError):
        Bme280Driver(bus, 0x77, sleep=NOSLEEP).read()  # nothing at 0x77


def sensirion_frame(raw_t: int, raw_h: int) -> bytes:
    t, h = struct.pack(">H", raw_t), struct.pack(">H", raw_h)
    return t + bytes([sensirion_crc8(t)]) + h + bytes([sensirion_crc8(h)])


def test_sensirion_crc_reference_value() -> None:
    assert sensirion_crc8(b"\xbe\xef") == 0x92  # from the Sensirion datasheets


def test_sht3x_and_sht4x() -> None:
    bus = FakeI2c()
    bus.raw[0x44] = sensirion_frame(0x6666, 0x8000)
    r = Sht3xDriver(bus, 0x44, sleep=NOSLEEP).read()
    assert r.values["temperature"] == pytest.approx(-45 + 175 * 0x6666 / 65535)
    assert r.values["humidity"] == pytest.approx(100 * 0x8000 / 65535)
    assert bus.writes[-1] == (0x44, (0x24, 0x00))
    r4 = Sht4xDriver(bus, 0x44, sleep=NOSLEEP).read()
    assert r4.values["humidity"] == pytest.approx(-6 + 125 * 0x8000 / 65535)
    assert bus.writes[-1] == (0x44, (0xFD,))
    bus.raw[0x44] = sensirion_frame(0x6666, 0xFFFF)
    assert Sht4xDriver(bus, 0x44, sleep=NOSLEEP).read().values["humidity"] == 100.0  # clamped


def test_sht_crc_error() -> None:
    bus = FakeI2c()
    frame = bytearray(sensirion_frame(0x6666, 0x8000))
    frame[2] ^= 0xFF
    bus.raw[0x44] = bytes(frame)
    with pytest.raises(IOError, match="CRC"):
        Sht3xDriver(bus, 0x44, sleep=NOSLEEP).read()


def test_parse_address() -> None:
    assert parse_address(None, 0x76) == 0x76
    assert parse_address(0x77, 0) == 0x77
    assert parse_address("0x44", 0) == 0x44
    assert parse_address("69", 0) == 69


@pytest.fixture
def fake_i2c():
    bus = FakeI2c()
    opened: List[int] = []

    def factory(n: int):
        opened.append(n)
        return bus

    set_bus_factory(factory)
    bus.opened = opened
    yield bus
    reset_bus_factory()


def test_config_opens_bus_lazily_and_shares_it(fake_i2c) -> None:
    fake_i2c.regs[0x76] = bme280_regs()
    fake_i2c.raw[0x44] = sensirion_frame(0x6666, 0x8000)
    pairs = parse_sensors({"sensors": {
        "air": {"type": "bme280", "address": "0x76"},
        "box": {"type": "SHT31", "bus": 1},
    }})
    assert fake_i2c.opened == []  # no bus I/O while parsing config
    (air_cfg, air), (_, box) = pairs
    assert sorted(e.alias for e in air_cfg.entities) == ["air_humidity", "air_pressure", "air_temperature"]
    air._sleep = box._sleep = NOSLEEP
    assert air.read().values["temperature"] == pytest.approx(25.08, abs=0.01)
    assert box.read().values["humidity"] == pytest.approx(50.0, abs=0.01)
    assert fake_i2c.opened == [1]  # one shared bus instance
    assert open_bus(1) is fake_i2c


def test_missing_smbus2_is_a_read_error_not_a_crash() -> None:
    def factory(n: int):
        raise RuntimeError("I2C sensors need smbus2")

    set_bus_factory(factory)
    try:
        [(_, drv)] = parse_sensors({"sensors": {"air": {"type": "bme280"}}})
        with pytest.raises(RuntimeError, match="smbus2"):
            drv.read()
    finally:
        reset_bus_factory()


# -- examples ----------------------------------------------------------------

def test_sensors_example_runs_with_fakes(tmp_path, fake_i2c) -> None:
    cfg = load_config(ROOT / "examples" / "sensors-i2c-onewire.yaml")
    assert sensors_configured(cfg)
    fake_i2c.regs[0x76] = bme280_regs()
    probe(tmp_path, "28-0316a2795f2b", w1_slave=W1_OK)
    for spec in cfg["sensors"].values():
        if spec["type"] == "ds18b20":
            spec["sysfs_root"] = str(tmp_path)
    pairs = parse_sensors(cfg)
    assert [sc.name for sc, _ in pairs] == ["air", "probe"]
    for _, drv in pairs:
        if hasattr(drv, "_sleep"):
            drv._sleep = NOSLEEP
        assert drv.read().numeric()


def test_schema_only_examples_load_without_drivers(caplog) -> None:
    """ADS1115 analog inputs and INA2xx power monitors are documented ahead of
    their drivers: configs load, the entries are skipped with a warning."""
    ana = load_config(ROOT / "examples" / "analog-inputs.yaml")
    ads = [p for p in ana["pins"] if p.get("source") == "ads1115"]
    assert ads and all({"address", "channel", "gain"} <= set(p) for p in ads)
    pm = load_config(ROOT / "examples" / "power-monitor.yaml")
    assert [sc.name for sc, _ in parse_sensors(pm)] == ["cpu"]  # battery (ina219) skipped
    assert "no driver for type 'ina219'" in caplog.text
