"""PWM channels: mock, software (RPi.GPIO), and hardware (Linux sysfs PWM).

A :class:`PwmChannel` takes a duty cycle in percent (0-100). Backends hand
out channels through ``GpioBackend.open_pwm(pin, frequency_hz, mode)``.

* ``software`` (default on a Pi): ``RPi.GPIO.PWM`` (or the rpi-lgpio drop-in).
  Timed by a thread, so expect jitter: fine for LEDs, fans, and motor speed,
  not for servos or anything that needs an exact pulse width.
* ``hardware``: the kernel PWM peripheral through
  ``/sys/class/pwm/pwmchip<N>``. It needs a ``dtoverlay`` that routes the pin
  to the PWM peripheral (see daemon.md). It is opt-in because a channel that
  is routed to a different pin than configured would drive the wrong pin.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Tuple

log = logging.getLogger(__name__)

PWM_MODES = ("software", "hardware")
SOFTWARE_PWM_ACCURATE_HZ = 1000

#: BCM pin -> sysfs channel for the Pi's two-channel PWM (Pi Zero/3/4: dtoverlay=pwm-2chan).
PI_HW_PWM_CHANNELS: Dict[int, int] = {12: 0, 18: 0, 13: 1, 19: 1}
#: Raspberry Pi 5 (RP1): four channels on GPIO 12, 13, 18, 19.
PI5_HW_PWM_CHANNELS: Dict[int, int] = {12: 0, 13: 1, 18: 2, 19: 3}


class PwmChannel(Protocol):
    kind: str  # "mock" | "software" | "hardware"

    def set_duty(self, percent: float) -> None: ...

    def set_frequency(self, hz: float) -> None: ...

    def stop(self) -> None: ...


def clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


class MockPwm:
    kind = "mock"

    def __init__(self, pin: int, frequency_hz: float, duty: float = 0.0) -> None:
        self.pin = pin
        self.frequency_hz = float(frequency_hz)
        self.duty = clamp_percent(duty)
        self.running = True
        self.history = [self.duty]

    def set_duty(self, percent: float) -> None:
        self.duty = clamp_percent(percent)
        self.history.append(self.duty)

    def set_frequency(self, hz: float) -> None:
        self.frequency_hz = float(hz)

    def stop(self) -> None:
        self.duty = 0.0
        self.running = False


class SoftwarePwm:
    """``RPi.GPIO.PWM`` wrapper (thread-timed)."""

    kind = "software"

    def __init__(self, gpio: Any, pin: int, frequency_hz: float, duty: float = 0.0) -> None:
        if frequency_hz > SOFTWARE_PWM_ACCURATE_HZ:
            log.warning(
                "GPIO%d: software PWM at %g Hz is inaccurate (jitter above ~%d Hz); "
                "consider pwm_mode: hardware on GPIO 12/13/18/19",
                pin, frequency_hz, SOFTWARE_PWM_ACCURATE_HZ,
            )
        self._gpio = gpio
        gpio.setup(pin, gpio.OUT, initial=gpio.LOW)
        self._pwm = gpio.PWM(pin, float(frequency_hz))
        self._pwm.start(clamp_percent(duty))

    def set_duty(self, percent: float) -> None:
        self._pwm.ChangeDutyCycle(clamp_percent(percent))

    def set_frequency(self, hz: float) -> None:
        self._pwm.ChangeFrequency(float(hz))

    def stop(self) -> None:
        self._pwm.stop()


class SysfsPwm:
    """Kernel PWM via ``/sys/class/pwm/pwmchip<chip>/pwm<channel>``."""

    kind = "hardware"

    def __init__(
        self,
        chip: int,
        channel: int,
        frequency_hz: float,
        duty: float = 0.0,
        root: Path = Path("/sys/class/pwm"),
        export_timeout_s: float = 1.0,
    ) -> None:
        self.chip_dir = Path(root) / f"pwmchip{chip}"
        if not self.chip_dir.is_dir():
            raise RuntimeError(
                f"{self.chip_dir} not found — enable the PWM overlay (dtoverlay=pwm-2chan,…) or use pwm_mode: software"
            )
        self.channel = channel
        self.dir = self.chip_dir / f"pwm{channel}"
        if not self.dir.is_dir():
            self._write(self.chip_dir / "export", channel)
            deadline = time.monotonic() + export_timeout_s
            # udev may take a moment to create the files and fix permissions.
            while not (self.dir / "period").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            if not (self.dir / "period").exists():
                raise RuntimeError(f"PWM channel {self.dir} did not appear after export")
        self._period_ns = 0
        self._duty = clamp_percent(duty)
        self.set_frequency(frequency_hz)
        self._write(self.dir / "enable", 1)

    @staticmethod
    def _write(path: Path, value: Any) -> None:
        path.write_text(f"{value}\n")

    def set_frequency(self, hz: float) -> None:
        if hz <= 0:
            raise ValueError("frequency_hz must be > 0")
        period = int(round(1e9 / float(hz)))
        # duty_cycle must never exceed period: lower duty first.
        self._write(self.dir / "duty_cycle", 0)
        self._write(self.dir / "period", period)
        self._period_ns = period
        self.set_duty(self._duty)

    def set_duty(self, percent: float) -> None:
        self._duty = clamp_percent(percent)
        self._write(self.dir / "duty_cycle", int(round(self._period_ns * self._duty / 100.0)))

    def stop(self) -> None:
        try:
            self._write(self.dir / "duty_cycle", 0)
            self._write(self.dir / "enable", 0)
            self._write(self.chip_dir / "unexport", self.channel)
        except OSError:  # pragma: no cover - best effort on shutdown
            log.debug("PWM unexport failed for %s", self.dir, exc_info=True)


def hardware_channel(board: Optional[str], pin: int, explicit: Optional[int] = None) -> Tuple[int, str]:
    """Return (channel, note) for a hardware PWM pin, or raise ValueError."""
    if explicit is not None:
        return int(explicit), "explicit pwm_channel"
    table = PI5_HW_PWM_CHANNELS if (board or "").lower() in ("pi5", "pi5b") else PI_HW_PWM_CHANNELS
    if pin not in table:
        raise ValueError(f"GPIO{pin} has no hardware PWM channel (use GPIO 12, 13, 18 or 19, or pwm_mode: software)")
    return table[pin], f"board {board or 'pi'} default"
