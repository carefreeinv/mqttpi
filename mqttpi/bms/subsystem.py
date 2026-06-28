"""BMS subsystem for the unified mqttpi daemon."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

from mqttpi.bms.bridge import build_publisher, poll_once

log = logging.getLogger(__name__)


class BmsSubsystem:
    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.cfg = cfg
        self._bms_cfg = cfg.get("bms", {})
        self._publisher = build_publisher(cfg)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._publisher.connect()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="mqttpi-bms",
            daemon=True,
        )
        self._thread.start()
        log.info(
            "BMS subsystem started (poll %ss, port %s)",
            self._bms_cfg.get("poll_interval", 30),
            self._bms_cfg.get("port"),
        )

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._publisher.publish_offline()
        self._publisher.disconnect()
        log.info("BMS subsystem stopped")

    def _poll_loop(self) -> None:
        poll_interval = float(self._bms_cfg.get("poll_interval", 30))
        retry_delay = float(self._bms_cfg.get("retry_delay", 10))

        while not self._stop.is_set():
            try:
                poll_once(self.cfg, self._publisher)
                self._wait(poll_interval)
            except Exception as exc:
                log.exception("BMS poll failed: %s", exc)
                self._publisher.publish_offline()
                self._wait(retry_delay)

    def _wait(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while not self._stop.is_set() and time.monotonic() < deadline:
            self._stop.wait(0.5)


def bms_enabled(cfg: Dict[str, Any]) -> bool:
    bms = cfg.get("bms")
    if not bms:
        return False
    return bool(bms.get("enabled", False))