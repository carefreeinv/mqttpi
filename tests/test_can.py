"""CAN: frame packing, field decoding, matching, reader thread, sensor wiring."""

from __future__ import annotations

import os
import queue
import socket
import time
from pathlib import Path
from typing import Optional

import pytest

from mqttpi.can.mapping import CanFrameDriver, FieldSpec, FrameMatcher
from mqttpi.can.transport import (
    CAN_ERR_BUSOFF,
    CAN_ERR_RESTARTED,
    CanFrame,
    CanReader,
    SocketCanTransport,
    pack_frame,
    reset_transport_factory,
    set_transport_factory,
    unpack_frame,
)
from mqttpi.config import load_config
from mqttpi.sensors.config import parse_sensors, sensors_configured

ROOT = Path(__file__).resolve().parents[1]


def wait_until(pred, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.005)
    return pred()


class FakeTransport:
    def __init__(self, channel: str = "can0") -> None:
        self.channel = channel
        self.q: "queue.Queue" = queue.Queue()
        self.closed = False

    def recv(self, timeout: float) -> Optional[CanFrame]:
        item = None
        try:
            item = self.q.get(timeout=min(timeout, 0.05))
        except queue.Empty:
            return None
        if isinstance(item, Exception):
            raise item
        return item

    def close(self) -> None:
        self.closed = True


# -- frames ------------------------------------------------------------------

def test_pack_unpack_roundtrip() -> None:
    for f in (CanFrame(0x123, b"\x01\x02", False), CanFrame(0x19FFB980, bytes(range(8)), True)):
        back = unpack_frame(pack_frame(f), timestamp=f.timestamp)
        assert (back.arbitration_id, back.data, back.is_extended) == (f.arbitration_id, f.data, f.is_extended)


def test_pgn_and_source_address() -> None:
    pdu2 = CanFrame(0x19FFB980, b"", True)  # priority 6, DGN 0x1FFB9, SA 0x80
    assert (pdu2.pgn, pdu2.source_address) == (0x1FFB9, 0x80)
    pdu1 = CanFrame(0x18EA2380, b"", True)  # PF 0xEA < 240: DA (0x23) not part of the PGN
    assert pdu1.pgn == 0x0EA00


# -- field decoding --------------------------------------------------------------

def test_field_decode_variants() -> None:
    data = bytes([0x10, 0x27, 0xFE, 0xFF, 0b00001000, 0xFF, 0x00, 0x01])
    assert FieldSpec.parse({"start_byte": 0, "length": 2, "scale": 0.01}, "f").decode(data) == pytest.approx(100.0)
    assert FieldSpec.parse({"start_byte": 6, "length": 2, "byte_order": "big"}, "f").decode(data) == 1
    assert FieldSpec.parse({"start_byte": 2, "length": 2, "signed": True}, "f").decode(data) == -2
    assert FieldSpec.parse({"start_byte": 4, "bit": 3}, "f").decode(data) == 1.0
    assert FieldSpec.parse({"start_byte": 4, "bit": 2}, "f").decode(data) == 0.0
    assert FieldSpec.parse({"start_byte": 5}, "f").decode(data) is None  # 0xFF = not available
    assert FieldSpec.parse({"start_byte": 5, "not_available": []}, "f").decode(data) == 255
    assert FieldSpec.parse({"start_byte": 1, "offset": -40}, "f").decode(data) == 39 - 40 + 0  # 0x27=39
    assert FieldSpec.parse({"start_byte": 6, "length": 2}, "f").decode(b"\x00\x00") is None  # short frame


def test_field_parse_errors() -> None:
    for bad in ({}, {"start_byte": 8}, {"start_byte": 6, "length": 4}, {"start_byte": 0, "bit": 8},
                {"start_byte": 0, "byte_order": "middle"}, {"start_byte": "x"}):
        with pytest.raises(ValueError):
            FieldSpec.parse(bad, "f")


def test_matcher() -> None:
    std = FrameMatcher(can_id=0x351, extended=False)
    assert std.matches(CanFrame(0x351, b"", False))
    assert not std.matches(CanFrame(0x351, b"", True))
    inst = FrameMatcher(pgn=0x1FFB9, extended=True, match={0: 1})
    assert inst.matches(CanFrame(0x19FFB980, b"\x01\x50", True))
    assert not inst.matches(CanFrame(0x19FFB980, b"\x00\x50", True))  # other instance
    assert not inst.matches(CanFrame(0x19FFB980, b"", True))
    sa = FrameMatcher(pgn=0x1FFB9, source_address=0x42, extended=True)
    assert not sa.matches(CanFrame(0x19FFB980, b"", True))


# -- reader thread ----------------------------------------------------------------

def test_reader_dispatches_despite_bad_listener() -> None:
    t = FakeTransport()
    reader = CanReader("can0", lambda ch: t)
    got = []
    reader.add_listener(lambda f: 1 / 0)
    reader.add_listener(got.append)
    reader.start()
    try:
        t.q.put(CanFrame(0x100, b"\x01"))
        assert wait_until(lambda: len(got) == 1)
        assert reader.connected.is_set() and reader.frames == 1
    finally:
        reader.stop()
    assert t.closed


def test_reader_reconnects_after_interface_errors(caplog) -> None:
    attempts = []
    transports = []

    def factory(ch):
        attempts.append(ch)
        if len(attempts) == 1:
            raise OSError(19, "No such device")
        t = FakeTransport(ch)
        transports.append(t)
        return t

    reader = CanReader("can0", factory, backoff_s=0.01, max_backoff_s=0.02)
    got = []
    reader.add_listener(got.append)
    reader.start()
    try:
        assert wait_until(lambda: transports)
        transports[0].q.put(OSError(100, "Network is down"))
        assert wait_until(lambda: len(transports) == 2)
        transports[1].q.put(CanFrame(0x100, b"\x02"))
        assert wait_until(lambda: got)
        assert "No such device" in caplog.text and "Network is down" in caplog.text
    finally:
        reader.stop()


def test_reader_bus_off_reporting(caplog) -> None:
    t = FakeTransport()
    reader = CanReader("can0", lambda ch: t)
    got = []
    reader.add_listener(got.append)
    reader.start()
    try:
        t.q.put(CanFrame(CAN_ERR_BUSOFF, bytes(8), is_error=True))
        assert wait_until(lambda: reader.bus_off)
        assert "bus-off" in caplog.text and not got  # error frames are not dispatched
        t.q.put(CanFrame(CAN_ERR_RESTARTED, bytes(8), is_error=True))
        assert wait_until(lambda: not reader.bus_off)
    finally:
        reader.stop()


# -- sensor driver ------------------------------------------------------------------

FRAME_SENSOR = {"type": "can_frame", "id": "0x351",
                "readings": {"voltage": {"start_byte": 0, "length": 2, "scale": 0.1,
                                         "ha": {"unit_of_measurement": "V", "device_class": "voltage"}},
                             "alarm": {"start_byte": 7, "bit": 0}}}


def test_driver_latest_frame_and_staleness() -> None:
    clock = [1000.0]
    t = FakeTransport()
    reader = CanReader("can0", lambda ch: t)
    drv = CanFrameDriver.from_config(dict(FRAME_SENSOR, max_age_s=5))
    drv._reader, drv._clock = reader, lambda: clock[0]
    with pytest.raises(IOError, match="no matching frame"):
        drv.read()
    drv.on_frame(CanFrame(0x351, bytes([0x2C, 0x01, 0, 0, 0, 0, 0, 1]), timestamp=999.0))
    drv.on_frame(CanFrame(0x352, bytes(8), timestamp=999.5))  # other id ignored
    r = drv.read()
    assert r.values == {"voltage": pytest.approx(30.0), "alarm": 1.0} and r.timestamp == 999.0
    clock[0] = 1010.0
    with pytest.raises(IOError, match="old"):
        drv.read()
    drv.close()


def test_driver_config_errors() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        CanFrameDriver.from_config({"type": "can_frame", "readings": {"v": {"start_byte": 0}}})
    with pytest.raises(ValueError, match="exactly one"):
        CanFrameDriver.from_config({"id": 1, "pgn": 2, "readings": {"v": {"start_byte": 0}}})
    with pytest.raises(ValueError, match="readings"):
        CanFrameDriver.from_config({"id": 1})
    assert CanFrameDriver.from_config({"id": 0x18FF0001, "readings": {"v": {"start_byte": 0}}}).matcher.extended


def test_end_to_end_through_shared_reader() -> None:
    transports = []

    def factory(ch):
        t = FakeTransport(ch)
        transports.append(t)
        return t

    set_transport_factory(factory)
    try:
        [(sc, drv)] = parse_sensors({"sensors": {"battery": FRAME_SENSOR}})
        assert not transports  # no socket while parsing config
        assert sorted(e.alias for e in sc.entities) == ["battery_alarm", "battery_voltage"]
        with pytest.raises(IOError):
            drv.read()  # starts the shared reader
        assert wait_until(lambda: transports)
        transports[0].q.put(CanFrame(0x351, bytes([0xE8, 0x03, 0, 0, 0, 0, 0, 0])))
        assert wait_until(lambda: _try(drv) == {"voltage": pytest.approx(100.0), "alarm": 0.0})
        drv.close()
    finally:
        reset_transport_factory()


def _try(drv):
    try:
        return drv.read().values
    except IOError:
        return None


# -- examples ------------------------------------------------------------------------

def test_can_frames_example_parses() -> None:
    cfg = load_config(ROOT / "examples" / "can-frames.yaml")
    assert sensors_configured(cfg)
    pairs = parse_sensors(cfg)
    names = [sc.name for sc, _ in pairs]
    assert names == ["battery", "engine", "switch_panel"]
    for _, drv in pairs:
        assert isinstance(drv, CanFrameDriver)


def test_documented_can_examples_still_load() -> None:
    for name in ("can-rvc.yaml", "can-vehicle.yaml", "can-can2040.yaml", "victron-vecan.yaml"):
        cfg = load_config(ROOT / "examples" / name)
        parse_sensors(cfg)  # top-level can: contracts are documented ahead of their decoders


# -- real SocketCAN on vcan0 (Linux with the vcan module) -------------------------------

def _vcan_available() -> bool:
    return hasattr(socket, "AF_CAN") and os.path.exists("/sys/class/net/vcan0")


@pytest.mark.skipif(not _vcan_available(), reason="needs vcan0: sudo modprobe vcan && "
                    "sudo ip link add dev vcan0 type vcan && sudo ip link set up vcan0")
def test_vcan0_roundtrip() -> None:
    rx = SocketCanTransport("vcan0")
    tx = SocketCanTransport("vcan0")
    try:
        tx.send(CanFrame(0x351, b"\xe8\x03"))
        tx.send(CanFrame(0x19FFB980, b"\x01\x50", True))
        got = [rx.recv(1.0), rx.recv(1.0)]
        assert [(f.arbitration_id, f.data, f.is_extended) for f in got] == [
            (0x351, b"\xe8\x03", False), (0x19FFB980, b"\x01\x50", True)]
        assert rx.recv(0.05) is None
    finally:
        rx.close()
        tx.close()
