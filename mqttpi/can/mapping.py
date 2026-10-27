"""Config-driven decoding of CAN frames into numeric readings.

One ``can_frame`` sensor = one frame (``id``, or ``pgn`` for 29-bit J1939-style
ids), optionally filtered by ``match`` bytes (e.g. an instance byte). Each
reading picks a field::

    readings:
      voltage: { start_byte: 0, length: 2, byte_order: little, scale: 0.01 }
      flags:   { start_byte: 4, bit: 3 }           # single bit → 0 / 1
      temp:    { start_byte: 2, length: 1, signed: true, offset: -40 }
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from mqttpi.can.transport import CanFrame, CanReader, get_reader, stop_readers
from mqttpi.sensors.model import Reading


def _int(value: Any, what: str) -> int:
    try:
        return value if isinstance(value, int) else int(str(value), 0)
    except (TypeError, ValueError):
        raise ValueError(f"{what}: {value!r} is not an integer") from None


@dataclass(frozen=True)
class FieldSpec:
    start_byte: int
    length: int = 1
    byte_order: str = "little"
    signed: bool = False
    bit: Optional[int] = None  # 0-7 within start_byte → 0/1
    scale: float = 1.0
    offset: float = 0.0
    #: raw values meaning "not available" (default: all bits set, J1939/RV-C style)
    not_available: Optional[List[int]] = None

    @classmethod
    def parse(cls, cfg: Mapping[str, Any], where: str) -> "FieldSpec":
        if "start_byte" not in cfg:
            raise ValueError(f"{where}: start_byte is required")
        start = _int(cfg["start_byte"], f"{where}.start_byte")
        length = _int(cfg.get("length", 1), f"{where}.length")
        bit = cfg.get("bit")
        if not 0 <= start <= 7 or not 1 <= length <= 8 or start + length > 8:
            raise ValueError(f"{where}: start_byte/length must stay within the 8 data bytes")
        if bit is not None and not 0 <= int(bit) <= 7:
            raise ValueError(f"{where}: bit must be 0-7")
        order = str(cfg.get("byte_order", "little")).lower()
        if order not in ("little", "big"):
            raise ValueError(f"{where}: byte_order must be little or big")
        na = cfg.get("not_available")
        return cls(start, length, order, bool(cfg.get("signed", False)),
                   int(bit) if bit is not None else None,
                   float(cfg.get("scale", 1.0)), float(cfg.get("offset", 0.0)),
                   [_int(v, f"{where}.not_available") for v in na] if isinstance(na, list) else None)

    def decode(self, data: bytes) -> Optional[float]:
        if len(data) < self.start_byte + self.length:
            return None
        chunk = data[self.start_byte:self.start_byte + self.length]
        if self.bit is not None:
            return float((chunk[0] >> self.bit) & 1)
        raw = int.from_bytes(chunk, self.byte_order, signed=False)
        na = self.not_available if self.not_available is not None else [(1 << (8 * self.length)) - 1]
        if raw in na:
            return None
        if self.signed and raw & (1 << (8 * self.length - 1)):
            raw -= 1 << (8 * self.length)
        return raw * self.scale + self.offset


@dataclass
class FrameMatcher:
    can_id: Optional[int] = None
    pgn: Optional[int] = None
    source_address: Optional[int] = None
    extended: Optional[bool] = None
    match: Dict[int, int] = field(default_factory=dict)  # byte index → value

    def matches(self, frame: CanFrame) -> bool:
        if self.extended is not None and frame.is_extended != self.extended:
            return False
        if self.can_id is not None and frame.arbitration_id != self.can_id:
            return False
        if self.pgn is not None:
            if not frame.is_extended or frame.pgn != self.pgn:
                return False
            if self.source_address is not None and frame.source_address != self.source_address:
                return False
        return all(len(frame.data) > i and frame.data[i] == v for i, v in self.match.items())


class CanFrameDriver:
    """``SensorDriver`` fed by a CAN reader: ``read()`` returns the latest
    decoded frame. No frame yet, or none for ``max_age_s`` → read error, so the
    entity goes unavailable through the normal staleness path."""

    def __init__(self, matcher: FrameMatcher, fields: Dict[str, FieldSpec], *, channel: str = "can0",
                 max_age_s: Optional[float] = None, reader: Optional[CanReader] = None,
                 clock=time.time) -> None:
        self.matcher, self.fields, self.channel = matcher, fields, channel
        self.max_age_s = max_age_s
        self._reader = reader
        self._latest: Optional[CanFrame] = None
        self._lock = threading.Lock()
        self._clock = clock
        self._attached = False

    @classmethod
    def from_config(cls, spec: Dict[str, Any]) -> "CanFrameDriver":
        where = f"sensors[{spec.get('name', 'can_frame')}]"
        if ("id" in spec) == ("pgn" in spec):
            raise ValueError(f"{where}: set exactly one of 'id' or 'pgn'")
        can_id = _int(spec["id"], f"{where}.id") if "id" in spec else None
        pgn = _int(spec["pgn"], f"{where}.pgn") if "pgn" in spec else None
        extended = spec.get("extended")
        if can_id is not None and extended is None:
            extended = can_id > 0x7FF
        match = {_int(k, f"{where}.match"): _int(v, f"{where}.match")
                 for k, v in (spec.get("match") or {}).items()}
        sa = spec.get("source_address")
        matcher = FrameMatcher(can_id, pgn, _int(sa, f"{where}.source_address") if sa is not None else None,
                               bool(extended) if extended is not None else (True if pgn is not None else None), match)
        readings = spec.get("readings") or {}
        if not readings:
            raise ValueError(f"{where}: readings with start_byte/length are required")
        fields = {str(k): FieldSpec.parse(v or {}, f"{where}.readings.{k}") for k, v in readings.items()}
        channel = str(spec.get("interface") or "can0")
        max_age = spec.get("max_age_s")
        return cls(matcher, fields, channel=channel, max_age_s=float(max_age) if max_age is not None else None)

    def _attach(self) -> None:
        if not self._attached:
            reader = self._reader or get_reader(self.channel)
            reader.add_listener(self.on_frame)
            self._reader = reader
            self._attached = True

    def on_frame(self, frame: CanFrame) -> None:
        if self.matcher.matches(frame):
            with self._lock:
                self._latest = frame

    def read(self) -> Reading:
        self._attach()  # first read starts the shared reader (not at config load)
        with self._lock:
            frame = self._latest
        if frame is None:
            raise IOError(f"CAN {self.channel}: no matching frame yet")
        if self.max_age_s is not None and self._clock() - frame.timestamp > self.max_age_s:
            raise IOError(f"CAN {self.channel}: last matching frame {self._clock() - frame.timestamp:.0f} s old")
        return Reading({k: f.decode(frame.data) for k, f in self.fields.items()}, timestamp=frame.timestamp)

    def close(self) -> None:
        """Daemon shutdown: stop the reader threads (idempotent; readers are
        shared per interface, so every CAN sensor stops together)."""
        if self._attached:
            stop_readers()
            if self._reader is not None:
                self._reader.stop()  # injected reader (not in the shared registry)
            self._attached = False
