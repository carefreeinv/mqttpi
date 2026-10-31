"""Build JBD BMS response frames for tests (per the public JBD UART protocol).

Response: DD <cmd> <status> <len> <data...> <crc_hi> <crc_lo> 77, with the
checksum over status + len + data (0x10000 minus the byte sum).
"""

from __future__ import annotations

from typing import List, Sequence

from mqttpi.bms.jbd_protocol import CMD_CELLINFO, CMD_HWINFO, PKT_END, PKT_START, chksum


def response(cmd: int, data: bytes, status: int = 0x00) -> bytes:
    body = bytes([status, len(data)]) + data
    crc = chksum(body)
    return bytes([PKT_START, cmd]) + body + bytes([(crc >> 8) & 0xFF, crc & 0xFF, PKT_END])


def u16(v: int) -> bytes:
    return int(v).to_bytes(2, "big")


def hwinfo_payload(
    voltage_10mv: int = 1330,
    current_10ma: int = -250,
    remaining_10mah: int = 8000,
    nominal_10mah: int = 10000,
    cycles: int = 42,
    balance: int = 0,
    protection: int = 0,
    version: int = 0x21,
    soc: int = 80,
    mos: int = 0x03,
    cells: int = 4,
    temps_dk: Sequence[int] = (2981, 2991),
) -> bytes:
    data = (
        u16(voltage_10mv)
        + int(current_10ma).to_bytes(2, "big", signed=True)
        + u16(remaining_10mah)
        + u16(nominal_10mah)
        + u16(cycles)
        + u16(0)  # production date
        + int(balance).to_bytes(4, "big")
        + u16(protection)
        + bytes([version, soc, mos, cells, len(temps_dk)])
    )
    for t in temps_dk:
        data += u16(t)
    return data


def cellinfo_payload(millivolts: List[int]) -> bytes:
    return b"".join(u16(mv) for mv in millivolts)


HWINFO_FRAME = response(CMD_HWINFO, hwinfo_payload())
CELLINFO_FRAME = response(CMD_CELLINFO, cellinfo_payload([3321, 3335, 3310, 3330]))
