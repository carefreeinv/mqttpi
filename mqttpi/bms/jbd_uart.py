"""JBD BMS client over wired UART."""

from __future__ import annotations

import logging
import time
from typing import Optional

import serial

from mqttpi.bms.jbd_protocol import (
    BmsData,
    CMD_CELLINFO,
    CMD_HWINFO,
    PKT_START,
    build_read_frame,
    parse_cellinfo,
    parse_frame,
    parse_hwinfo,
)

log = logging.getLogger(__name__)


class JbdUartClient:
    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        response_timeout: float = 2.0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.response_timeout = response_timeout
        self._ser: Optional[serial.Serial] = None

    def open(self) -> None:
        self._ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )
        self._ser.reset_input_buffer()
        log.info("Opened %s at %d baud", self.port, self.baudrate)

    def close(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None

    def read_all(self) -> BmsData:
        if not self._ser or not self._ser.is_open:
            raise ConnectionError("Serial port not open")

        hw = self._request(CMD_HWINFO)
        cells = self._request(CMD_CELLINFO)
        data = parse_hwinfo(hw)
        parse_cellinfo(cells, data)
        data.online = True
        return data

    def _request(self, address: int) -> bytes:
        assert self._ser is not None
        self._ser.reset_input_buffer()
        self._ser.write(build_read_frame(address))
        self._ser.flush()
        frame = self._read_frame(expected_function=address)
        function, payload = parse_frame(frame)
        if function != address:
            raise ValueError(
                f"Unexpected response 0x{function:02X} for request 0x{address:02X}"
            )
        return payload

    def _read_frame(self, expected_function: int) -> bytes:
        assert self._ser is not None
        buffer = bytearray()
        deadline = time.monotonic() + self.response_timeout

        while time.monotonic() < deadline:
            chunk = self._ser.read(128)
            if chunk:
                buffer.extend(chunk)

            while buffer and buffer[0] != PKT_START:
                buffer.pop(0)

            if len(buffer) < 4:
                continue

            data_len = buffer[3]
            frame_len = 4 + data_len + 3
            if len(buffer) < frame_len:
                continue

            frame = bytes(buffer[:frame_len])
            if frame[1] == expected_function and frame[2] == 0x00:
                return frame

            buffer.pop(0)

        raise TimeoutError(
            f"No valid JBD response for 0x{expected_function:02X} "
            f"within {self.response_timeout}s"
        )