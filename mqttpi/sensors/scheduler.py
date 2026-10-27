"""One scheduler thread polls every sensor at its own interval.

Reads run in a worker pool (one worker per sensor), so a slow or hung driver
only delays itself: a read still running after ``timeout_s`` counts as a
failure, its eventual result is discarded, and the sensor is not polled again
until that read returns. Callbacks (``on_reading``, ``on_failure``,
``on_stale``) all run on the scheduler thread.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from mqttpi.sensors.model import QUALITY_BAD, Reading, SensorDriver

log = logging.getLogger(__name__)


@dataclass
class ScheduledSensor:
    name: str
    driver: SensorDriver
    interval_s: float
    timeout_s: float
    stale_after_s: float
    # runtime state
    next_due: float = 0.0
    inflight: Optional["Future[Reading]"] = None
    inflight_since: float = 0.0
    timed_out: bool = False
    last_good: Optional[float] = None
    started_at: float = 0.0
    stale: bool = True  # unavailable until the first good reading
    stale_reported: bool = False
    failures: int = 0
    reads: int = field(default=0)


ReadingCb = Callable[[ScheduledSensor, Reading], None]
FailureCb = Callable[[ScheduledSensor, str], None]
StaleCb = Callable[[ScheduledSensor], None]


class SensorScheduler:
    def __init__(
        self,
        sensors: List[ScheduledSensor],
        on_reading: ReadingCb,
        on_failure: Optional[FailureCb] = None,
        on_stale: Optional[StaleCb] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.sensors = sensors
        self.on_reading = on_reading
        self.on_failure = on_failure or (lambda s, why: None)
        self.on_stale = on_stale or (lambda s: None)
        self.clock = clock
        self._pool = ThreadPoolExecutor(max_workers=max(1, len(sensors)), thread_name_prefix="mqttpi-sensor")
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        now = clock()
        for s in sensors:
            s.next_due = now
            s.started_at = now

    # -- lifecycle -------------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="mqttpi-sensors", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)
        # Do not wait for hung drivers; worker threads are daemonic-ish.
        self._pool.shutdown(wait=False)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                wait = self.tick(self.clock()) - self.clock()
            except Exception:  # pragma: no cover - never kill the loop
                log.exception("Sensor scheduler error")
                wait = 1.0
            self._wake.wait(max(0.0, min(wait, 5.0)))
            self._wake.clear()

    # -- one pass (public for tests) ------------------------------------
    def tick(self, now: float) -> float:
        """Collect finished reads, enforce timeouts, start due reads, check
        staleness. Returns the monotonic time of the next deadline."""
        deadlines: List[float] = []
        for s in self.sensors:
            if s.inflight is not None:
                if s.inflight.done():
                    self._collect(s, now)
                elif not s.timed_out and now - s.inflight_since >= s.timeout_s:
                    s.timed_out = True
                    self._fail(s, f"timeout after {s.timeout_s:g}s")
            if s.inflight is None and now >= s.next_due:
                self._submit(s, now)
            if s.inflight is not None and not s.timed_out:
                deadlines.append(s.inflight_since + s.timeout_s)
            deadlines.append(s.next_due)

            ref = s.last_good if s.last_good is not None else s.started_at
            if not s.stale_reported and now - ref >= s.stale_after_s:
                s.stale = True
                s.stale_reported = True
                log.warning("Sensor %s: no good reading for %.0fs — marking unavailable", s.name, now - ref)
                self.on_stale(s)
            elif not s.stale_reported:
                deadlines.append(ref + s.stale_after_s)
        return min(deadlines) if deadlines else now + 1.0

    def _submit(self, s: ScheduledSensor, now: float) -> None:
        s.inflight = self._pool.submit(s.driver.read)
        s.inflight.add_done_callback(lambda _f: self._wake.set())
        s.inflight_since = now
        s.timed_out = False
        s.reads += 1
        # Keep cadence; if we fell behind, restart from now.
        s.next_due = s.next_due + s.interval_s if s.next_due + s.interval_s > now else now + s.interval_s

    def _collect(self, s: ScheduledSensor, now: float) -> None:
        fut, s.inflight = s.inflight, None
        assert fut is not None
        if s.timed_out:
            log.debug("Sensor %s: discarding late result", s.name)
            return
        try:
            reading = fut.result()
        except Exception as exc:  # driver raised
            self._fail(s, f"{type(exc).__name__}: {exc}")
            return
        if not isinstance(reading, Reading) or reading.quality == QUALITY_BAD or not reading.numeric():
            self._fail(s, "bad or empty reading")
            return
        s.failures = 0
        s.last_good = now
        s.stale = False
        s.stale_reported = False
        self.on_reading(s, reading)

    def _fail(self, s: ScheduledSensor, why: str) -> None:
        s.failures += 1
        level = logging.WARNING if s.failures in (1, 10) or s.failures % 100 == 0 else logging.DEBUG
        log.log(level, "Sensor %s read failed (%d in a row): %s", s.name, s.failures, why)
        self.on_failure(s, why)
