"""JBD / Jiabaida BMS protocol — framing and parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

PKT_START = 0xDD
PKT_END = 0x77
CMD_READ = 0xA5

CMD_HWINFO = 0x03
CMD_CELLINFO = 0x04

ERRORS = [
    "Cell overvoltage",
    "Cell undervoltage",
    "Pack overvoltage",
    "Pack undervoltage",
    "Charging over temperature",
    "Charging under temperature",
    "Discharging over temperature",
    "Discharging under temperature",
    "Charging overcurrent",
    "Discharging overcurrent",
    "Short circuit",
    "IC front-end error",
    "Mosfet software lock",
    "Charge timeout",
]


def chksum(data: bytes) -> int:
    checksum = 0
    for b in data:
        checksum = (checksum - b) & 0xFFFF
    return checksum


def build_read_frame(address: int) -> bytes:
    body = bytes([CMD_READ, address, 0x00])
    crc = chksum(body)
    return bytes([PKT_START]) + body + bytes([(crc >> 8) & 0xFF, crc & 0xFF, PKT_END])


def parse_frame(raw: bytes) -> tuple[int, bytes]:
    if len(raw) < 7 or raw[0] != PKT_START or raw[-1] != PKT_END:
        raise ValueError("Invalid JBD frame boundaries")
    function = raw[1]
    data_len = raw[3]
    frame_len = 4 + data_len + 3
    if len(raw) != frame_len:
        raise ValueError(f"Frame length mismatch: expected {frame_len}, got {len(raw)}")
    expected = chksum(raw[2 : 2 + data_len + 2])
    remote = (raw[frame_len - 3] << 8) | raw[frame_len - 2]
    if expected != remote:
        raise ValueError(f"CRC mismatch: expected 0x{expected:04X}, got 0x{remote:04X}")
    return function, raw[4 : frame_len - 3]


def _get16(data: bytes, offset: int) -> int:
    return (data[offset] << 8) | data[offset + 1]


def _bitmask_labels(labels: List[str], mask: int) -> str:
    active = [labels[i] for i in range(len(labels)) if mask & (1 << i)]
    return ", ".join(active) if active else "none"


@dataclass
class BmsData:
    total_voltage: float = 0.0
    current: float = 0.0
    power: float = 0.0
    soc: int = 0
    capacity_remaining_ah: float = 0.0
    nominal_capacity_ah: float = 0.0
    cycle_count: int = 0
    cell_count: int = 0
    cell_voltages: List[float] = field(default_factory=list)
    min_cell_voltage: float = 0.0
    max_cell_voltage: float = 0.0
    min_cell_number: int = 0
    max_cell_number: int = 0
    delta_cell_voltage: float = 0.0
    avg_cell_voltage: float = 0.0
    temperatures_c: List[float] = field(default_factory=list)
    balancing: bool = False
    balancing_cells: str = ""
    charging: bool = False
    discharging: bool = False
    protection_active: bool = False
    protection_flags: str = "none"
    protection_bitmask: int = 0
    software_version: float = 0.0
    device_model: str = ""
    online: bool = False


def parse_hwinfo(data: bytes) -> BmsData:
    result = BmsData()
    if len(data) < 24:
        raise ValueError(f"Hardware info frame too short ({len(data)} bytes)")

    result.total_voltage = _get16(data, 0) * 0.01
    result.current = int.from_bytes(data[2:4], "big", signed=True) * 0.01
    result.power = result.total_voltage * result.current
    result.capacity_remaining_ah = _get16(data, 4) * 0.01
    result.nominal_capacity_ah = _get16(data, 6) * 0.01
    result.cycle_count = _get16(data, 8)
    balance_mask = int.from_bytes(data[12:16], "big")
    result.protection_bitmask = _get16(data, 16)
    result.protection_active = result.protection_bitmask != 0
    result.protection_flags = _bitmask_labels(ERRORS, result.protection_bitmask)
    result.software_version = (data[18] >> 4) + ((data[18] & 0x0F) * 0.1)
    result.soc = data[19]
    mos = data[20]
    result.charging = bool(mos & 0x01)
    result.discharging = bool(mos & 0x02)
    result.cell_count = data[21]
    temp_count = min(data[22], 6)
    result.temperatures_c = [
        (_get16(data, 23 + i * 2) - 2731) * 0.1 for i in range(temp_count)
    ]
    balancing_cells: List[str] = []
    for i in range(result.cell_count):
        if balance_mask & (1 << (result.cell_count - 1 - i)):
            balancing_cells.append(str(i + 1))
    result.balancing = bool(balance_mask)
    result.balancing_cells = ", ".join(balancing_cells)
    return result


def parse_cellinfo(data: bytes, result: BmsData) -> None:
    if len(data) < 2 or len(data) % 2:
        raise ValueError(f"Invalid cell info frame ({len(data)} bytes)")

    cells = min(len(data) // 2, 32)
    voltages = [_get16(data, i * 2) * 0.001 for i in range(cells)]
    result.cell_voltages = voltages[: result.cell_count or cells]
    if not result.cell_voltages:
        return
    result.min_cell_voltage = min(result.cell_voltages)
    result.max_cell_voltage = max(result.cell_voltages)
    result.min_cell_number = result.cell_voltages.index(result.min_cell_voltage) + 1
    result.max_cell_number = result.cell_voltages.index(result.max_cell_voltage) + 1
    result.delta_cell_voltage = result.max_cell_voltage - result.min_cell_voltage
    result.avg_cell_voltage = sum(result.cell_voltages) / len(result.cell_voltages)