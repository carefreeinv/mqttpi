"""SocketCAN transport (stdlib ``socket.AF_CAN``; no extra dependency) and a
reader thread with reconnect and bus-off detection.

mqttpi does not configure the interface; bring it up first, e.g.::

    sudo ip link set can0 up type can bitrate 250000 restart-ms 100
"""

from __future__ import annotations

import logging
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Protocol

log = logging.getLogger(__name__)

CAN_EFF_FLAG = 0x80000000
CAN_RTR_FLAG = 0x40000000
CAN_ERR_FLAG = 0x20000000
CAN_EFF_MASK = 0x1FFFFFFF
CAN_SFF_MASK = 0x000007FF
CAN_ERR_CRTL = 0x00000004
CAN_ERR_BUSOFF = 0x00000040
CAN_ERR_RESTARTED = 0x00000100
_FRAME = struct.Struct("=IB3x8s")


@dataclass(frozen=True)
class CanFrame:
    arbitration_id: int
    data: bytes
    is_extended: bool = False
    timestamp: float = field(default_factory=time.time)
    is_error: bool = False
    is_remote: bool = False

    @property
    def pgn(self) -> int:
        """J1939-style parameter group number of a 29-bit id (PDU1 → DA cleared)."""
        pf = (self.arbitration_id >> 16) & 0xFF
        pgn = (self.arbitration_id >> 8) & 0x3FFFF
        return pgn & 0x3FF00 if pf < 240 else pgn

    @property
    def source_address(self) -> int:
        return self.arbitration_id & 0xFF


def pack_frame(frame: CanFrame) -> bytes:
    can_id = frame.arbitration_id | (CAN_EFF_FLAG if frame.is_extended else 0)
    return _FRAME.pack(can_id, len(frame.data), frame.data.ljust(8, b"\x00"))


def unpack_frame(raw: bytes, timestamp: Optional[float] = None) -> CanFrame:
    can_id, dlc, data = _FRAME.unpack(raw[:16])
    extended = bool(can_id & CAN_EFF_FLAG)
    return CanFrame(
        arbitration_id=can_id & (CAN_EFF_MASK if extended else CAN_SFF_MASK),
        data=data[:dlc],
        is_extended=extended,
        timestamp=time.time() if timestamp is None else timestamp,
        is_error=bool(can_id & CAN_ERR_FLAG),
        is_remote=bool(can_id & CAN_RTR_FLAG),
    )


class CanTransport(Protocol):
    def recv(self, timeout: float) -> Optional[CanFrame]: ...

    def close(self) -> None: ...


class SocketCanTransport:
    """Raw CAN socket bound to ``channel`` (``can0``, ``vcan0``). Receives
    error frames too, so bus-off is reported."""

    def __init__(self, channel: str) -> None:
        if not hasattr(socket, "AF_CAN"):  # pragma: no cover - non-Linux
            raise OSError("SocketCAN needs Linux")
        self.channel = channel
        self._sock = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        try:
            self._sock.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_ERR_FILTER,
                                  struct.pack("=I", CAN_ERR_BUSOFF | CAN_ERR_CRTL | CAN_ERR_RESTARTED))
            self._sock.bind((channel,))
        except OSError:
            self._sock.close()
            raise

    def recv(self, timeout: float) -> Optional[CanFrame]:
        self._sock.settimeout(timeout)
        try:
            raw = self._sock.recv(16)
        except socket.timeout:
            return None
        return unpack_frame(raw)

    def send(self, frame: CanFrame) -> None:
        self._sock.send(pack_frame(frame))

    def close(self) -> None:
        self._sock.close()


Listener = Callable[[CanFrame], None]
TransportFactory = Callable[[str], CanTransport]


class CanReader:
    """Background reader for one interface: dispatches frames to listeners,
    reopens the socket with backoff when the interface goes away."""

    def __init__(self, channel: str, factory: TransportFactory = SocketCanTransport, *,
                 recv_timeout_s: float = 1.0, backoff_s: float = 1.0, max_backoff_s: float = 30.0) -> None:
        self.channel = channel
        self._factory = factory
        self._recv_timeout_s = recv_timeout_s
        self._backoff_s, self._max_backoff_s = backoff_s, max_backoff_s
        self._listeners: List[Listener] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.connected = threading.Event()
        self.frames = 0
        self.bus_off = False
        self.last_error: Optional[str] = None

    def add_listener(self, fn: Listener) -> None:
        with self._lock:
            self._listeners.append(fn)

    def start(self) -> None:
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name=f"mqttpi-can-{self.channel}", daemon=True)
                self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        delay = self._backoff_s
        while not self._stop.is_set():
            try:
                transport = self._factory(self.channel)
            except OSError as exc:
                self._down(f"cannot open {self.channel}: {exc}")
                self._stop.wait(delay)
                delay = min(delay * 2, self._max_backoff_s)
                continue
            log.info("CAN %s: listening", self.channel)
            self.connected.set()
            self.last_error = None
            delay = self._backoff_s
            try:
                while not self._stop.is_set():
                    frame = transport.recv(self._recv_timeout_s)
                    if frame is not None:
                        self._dispatch(frame)
            except OSError as exc:  # interface down / removed
                self._down(f"{self.channel} read failed: {exc}")
                self._stop.wait(delay)
            finally:
                try:
                    transport.close()
                except OSError:  # pragma: no cover
                    pass

    def _down(self, message: str) -> None:
        self.connected.clear()
        if message != self.last_error:
            log.warning("CAN %s (retrying)", message)
        self.last_error = message

    def _dispatch(self, frame: CanFrame) -> None:
        if frame.is_error:
            # Error class in the id; details in data. Bus-off = wrong bitrate,
            # no other node acking, or wiring/termination fault.
            if frame.arbitration_id & CAN_ERR_BUSOFF:
                if not self.bus_off:
                    log.error("CAN %s: bus-off (check bitrate, termination, wiring; "
                              "'restart-ms 100' lets the kernel recover)", self.channel)
                self.bus_off = True
            elif frame.arbitration_id & CAN_ERR_RESTARTED:
                log.info("CAN %s: controller restarted", self.channel)
                self.bus_off = False
            return
        if self.bus_off:
            log.info("CAN %s: traffic again after bus-off", self.channel)
            self.bus_off = False
        self.frames += 1
        with self._lock:
            listeners = list(self._listeners)
        for fn in listeners:
            try:
                fn(frame)
            except Exception:  # a bad decoder must not stop the reader
                log.exception("CAN %s: listener failed", self.channel)


_readers: Dict[str, CanReader] = {}
_readers_lock = threading.Lock()
_reader_factory: TransportFactory = SocketCanTransport


def get_reader(channel: str) -> CanReader:
    """Shared, started reader per interface."""
    with _readers_lock:
        reader = _readers.get(channel)
        if reader is None:
            reader = _readers[channel] = CanReader(channel, _reader_factory)
        reader.start()
        return reader


def set_transport_factory(factory: TransportFactory) -> None:
    """Tests / custom transports. Stops and forgets existing readers."""
    global _reader_factory
    with _readers_lock:
        for r in _readers.values():
            r.stop()
        _readers.clear()
        _reader_factory = factory


def reset_transport_factory() -> None:
    set_transport_factory(SocketCanTransport)


def stop_readers() -> None:
    with _readers_lock:
        for r in _readers.values():
            r.stop()
        _readers.clear()
