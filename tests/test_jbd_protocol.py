"""JBD protocol framing/parsing and the UART client (fake serial port)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mqttpi.bms import jbd_uart
from mqttpi.bms.jbd_protocol import (
    CMD_CELLINFO,
    CMD_HWINFO,
    BmsData,
    build_read_frame,
    chksum,
    parse_cellinfo,
    parse_frame,
    parse_hwinfo,
)
from tests.jbd_frames import CELLINFO_FRAME, HWINFO_FRAME, cellinfo_payload, hwinfo_payload, response


DOC_FRAMES = {
    line.split()[0]: bytes.fromhex("".join(line.split()[1:]))
    for line in (Path(__file__).parent / "data" / "jbd_doc_frames.txt").read_text().splitlines()
    if line.strip() and not line.startswith("#")
}


def test_checksum() -> None:
    assert chksum(b"") == 0
    assert chksum(bytes([0x03, 0x00])) == 0xFFFD


def test_read_frames_match_protocol_document() -> None:
    assert build_read_frame(CMD_HWINFO) == DOC_FRAMES["request_hwinfo"]
    assert build_read_frame(CMD_CELLINFO) == DOC_FRAMES["request_cellinfo"]
    assert build_read_frame(0x05) == bytes.fromhex("DDA50500FFFB77")  # hardware version


def test_parse_protocol_document_response() -> None:
    fn, data = parse_frame(DOC_FRAMES["response_hwinfo"])
    assert fn == CMD_HWINFO
    d = parse_hwinfo(data)
    assert d.total_voltage == pytest.approx(58.88)
    assert d.current == 0
    assert d.capacity_remaining_ah == pytest.approx(7.2)
    assert d.nominal_capacity_ah == pytest.approx(10.0)
    assert d.cycle_count == 0
    assert d.software_version == pytest.approx(1.0)
    assert d.soc == 72
    assert d.charging and d.discharging
    assert d.cell_count == 15
    assert d.temperatures_c == pytest.approx([20.3, 21.5])
    assert d.protection_flags == "none" and not d.balancing


def test_parse_frame_roundtrip() -> None:
    fn, data = parse_frame(HWINFO_FRAME)
    assert fn == CMD_HWINFO and data == hwinfo_payload()


@pytest.mark.parametrize("raw, msg", [
    (b"\xdd\x03", "boundaries"),
    (HWINFO_FRAME[:-1] + b"\x00", "boundaries"),
    (HWINFO_FRAME[:-3] + HWINFO_FRAME[-1:], "length"),
])
def test_parse_frame_rejects_malformed(raw, msg) -> None:
    with pytest.raises(ValueError, match=msg):
        parse_frame(raw)


def test_parse_frame_rejects_bad_crc() -> None:
    bad = bytearray(HWINFO_FRAME)
    bad[5] ^= 0xFF
    with pytest.raises(ValueError, match="CRC"):
        parse_frame(bytes(bad))


def test_parse_hwinfo_fields() -> None:
    d = parse_hwinfo(hwinfo_payload())
    assert d.total_voltage == pytest.approx(13.30)
    assert d.current == pytest.approx(-2.50)
    assert d.power == pytest.approx(-33.25)
    assert d.capacity_remaining_ah == pytest.approx(80.0)
    assert d.nominal_capacity_ah == pytest.approx(100.0)
    assert d.cycle_count == 42
    assert d.soc == 80
    assert d.software_version == pytest.approx(2.1)
    assert d.charging and d.discharging
    assert d.cell_count == 4
    assert d.temperatures_c == pytest.approx([25.0, 26.0])
    assert not d.protection_active and d.protection_flags == "none"
    assert not d.balancing and d.balancing_cells == ""


def test_parse_hwinfo_protection_flags_and_mosfets() -> None:
    d = parse_hwinfo(hwinfo_payload(protection=0b101, mos=0x00))
    assert d.protection_active and d.protection_bitmask == 5
    assert d.protection_flags == "Cell overvoltage, Pack overvoltage"
    assert not d.charging and not d.discharging


def test_parse_hwinfo_balancing_cells_follow_protocol() -> None:
    d = parse_hwinfo(hwinfo_payload(balance=0b0001 << 16, cells=4))  # low word bit 0
    assert d.balancing and d.balancing_cells == "1"
    d = parse_hwinfo(hwinfo_payload(balance=0b0110 << 16, cells=4))
    assert d.balancing_cells == "2, 3"
    d = parse_hwinfo(hwinfo_payload(balance=0b1, cells=20))  # high word bit 0
    assert d.balancing_cells == "17"


def test_parse_hwinfo_caps_temperature_sensors_at_six() -> None:
    d = parse_hwinfo(hwinfo_payload(temps_dk=[2731] * 8))
    assert len(d.temperatures_c) == 6


def test_parse_hwinfo_too_short() -> None:
    with pytest.raises(ValueError, match="too short"):
        parse_hwinfo(b"\x00" * 10)


def test_parse_cellinfo_stats() -> None:
    d = BmsData(cell_count=4)
    parse_cellinfo(cellinfo_payload([3321, 3335, 3310, 3330]), d)
    assert d.cell_voltages == pytest.approx([3.321, 3.335, 3.310, 3.330])
    assert (d.min_cell_number, d.max_cell_number) == (3, 2)
    assert d.delta_cell_voltage == pytest.approx(0.025)
    assert d.avg_cell_voltage == pytest.approx(3.324)


def test_parse_cellinfo_trims_to_cell_count_and_validates() -> None:
    d = BmsData(cell_count=2)
    parse_cellinfo(cellinfo_payload([3300, 3301, 3302]), d)
    assert len(d.cell_voltages) == 2
    with pytest.raises(ValueError):
        parse_cellinfo(b"\x01", BmsData())


class FakeSerial:
    """Replies to JBD read requests with canned frames, optionally in pieces."""

    def __init__(self, replies, chunk=5, garbage=b"") -> None:
        self.replies = dict(replies)
        self.chunk = chunk
        self.garbage = garbage
        self.rx = bytearray()
        self.written = []
        self.is_open = True

    def reset_input_buffer(self) -> None:
        self.rx.clear()

    def write(self, frame: bytes) -> None:
        self.written.append(frame)
        reply = self.replies.get(frame[2])
        if reply is not None:
            self.rx.extend(self.garbage + reply)

    def flush(self) -> None:
        pass

    def read(self, n: int) -> bytes:
        n = min(n, self.chunk)
        out, self.rx = bytes(self.rx[:n]), self.rx[n:]
        return out

    def close(self) -> None:
        self.is_open = False


def client_with(fake) -> jbd_uart.JbdUartClient:
    c = jbd_uart.JbdUartClient("/dev/fake", response_timeout=0.3)
    c._ser = fake  # type: ignore[assignment]
    return c


def test_uart_read_all_reassembles_chunked_frames_and_skips_garbage() -> None:
    fake = FakeSerial({CMD_HWINFO: HWINFO_FRAME, CMD_CELLINFO: CELLINFO_FRAME},
                      chunk=3, garbage=b"\x00\x13")
    d = client_with(fake).read_all()
    assert d.online and d.soc == 80 and len(d.cell_voltages) == 4
    assert fake.written == [build_read_frame(CMD_HWINFO), build_read_frame(CMD_CELLINFO)]


def test_uart_timeout_when_bms_silent() -> None:
    with pytest.raises(TimeoutError):
        client_with(FakeSerial({})).read_all()


def test_uart_error_status_frame_is_not_accepted() -> None:
    fake = FakeSerial({CMD_HWINFO: response(CMD_HWINFO, hwinfo_payload(), status=0x80)})
    with pytest.raises(TimeoutError):
        client_with(fake).read_all()


def test_uart_not_open() -> None:
    with pytest.raises(ConnectionError):
        jbd_uart.JbdUartClient("/dev/fake").read_all()


def test_uart_open_uses_8n1(monkeypatch) -> None:
    seen = {}

    class S(FakeSerial):
        def __init__(self, **kw) -> None:
            seen.update(kw)
            super().__init__({})

    monkeypatch.setattr(jbd_uart.serial, "Serial", S)
    c = jbd_uart.JbdUartClient("/dev/ttyS0", baudrate=9600)
    c.open()
    assert seen["port"] == "/dev/ttyS0" and seen["baudrate"] == 9600
    assert (seen["bytesize"], seen["parity"], seen["stopbits"]) == (8, "N", 1)
    c.close()
    assert c._ser is None
