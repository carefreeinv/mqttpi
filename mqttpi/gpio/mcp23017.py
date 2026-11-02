"""MCP23017 16-bit I2C GPIO expander, exposed through the ``GpioBackend`` interface.

Pins on an expander are addressed as ``ExpanderPin(chip=0x20, pin=0..15)``
(0–7 = port A, 8–15 = port B). ``ExpanderBackend`` routes those to the right
chip and every native ``int`` pin to the wrapped native backend, so the GPIO
manager stays backend-agnostic.

Registers are used in the power-on layout (``IOCON.BANK = 0``). Inputs are
polled (no interrupt line); the chip only has pull-ups.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Sequence, Union

from mqttpi.gpio.backend import GpioBackend
from mqttpi.gpio.pwm import PwmChannel
from mqttpi.sensors.i2c import I2cBus

log = logging.getLogger(__name__)

IODIR = 0x00  # 1 = input (power-on: 0xFFFF)
IPOL = 0x02
GPINTEN = 0x04
IOCON = 0x0A
GPPU = 0x0C  # 1 = 100 kΩ pull-up
GPIO = 0x12
OLAT = 0x14
VALID_ADDRESSES = range(0x20, 0x28)


@dataclass(frozen=True)
class ExpanderPin:
    chip: int  # I2C address
    pin: int  # 0..15

    def __str__(self) -> str:
        port = "A" if self.pin < 8 else "B"
        return f"0x{self.chip:02x}:GP{port}{self.pin % 8}"


PinRef = Union[int, ExpanderPin]


def parse_expander_pin(value: Any, where: str) -> int:
    """``0..15``, or ``"A0".."B7"`` / ``"GPA0".."GPB7"``."""
    if isinstance(value, str) and not value.strip().isdigit():
        v = value.strip().upper().replace("GP", "", 1)
        if len(v) == 2 and v[0] in "AB" and v[1] in "01234567":
            return (0 if v[0] == "A" else 8) + int(v[1])
        raise ValueError(f"{where}: expander pin {value!r} must be 0-15 or A0-B7")
    n = int(value)
    if not 0 <= n <= 15:
        raise ValueError(f"{where}: expander pin {n} must be 0-15")
    return n


class Mcp23017:
    """One chip. Keeps shadow copies of IODIR/GPPU/OLAT and re-applies them
    after an I2C error or when a periodic check finds the chip was reset
    (a brown-out returns every pin to an input with outputs latched low)."""

    def __init__(self, bus: I2cBus, address: int, *, read_cache_s: float = 0.005,
                 verify_interval_s: float = 5.0, clock=time.monotonic) -> None:
        if address not in VALID_ADDRESSES:
            raise ValueError(f"MCP23017 address 0x{address:02x} outside 0x20-0x27")
        self.bus, self.address = bus, address
        self.iodir = 0xFFFF
        self.gppu = 0x0000
        self.olat = 0x0000
        self._lock = threading.Lock()
        self._cache: Optional[int] = None
        self._cache_at = 0.0
        self._read_cache_s = read_cache_s
        self._verify_interval_s = verify_interval_s
        self._verified_at = 0.0
        self._dirty = True  # registers need (re)writing
        self._clock = clock
        self.reinit_count = 0

    # -- register helpers (A then B: sequential addressing) ----------------
    def _write16(self, reg: int, value: int) -> None:
        self.bus.write(self.address, [reg, value & 0xFF, (value >> 8) & 0xFF])

    def _read16(self, reg: int) -> int:
        lo, hi = self.bus.write_read(self.address, [reg], 2)
        return lo | (hi << 8)

    def _apply(self) -> None:
        # OLAT before IODIR so a pin turning into an output starts at its level.
        self._write16(IOCON, 0x00)
        self._write16(IPOL, 0x0000)
        self._write16(GPINTEN, 0x0000)
        self._write16(OLAT, self.olat)
        self._write16(GPPU, self.gppu)
        self._write16(IODIR, self.iodir)
        self._dirty = False
        self._verified_at = self._clock()

    def _ensure(self) -> None:
        if self._dirty:
            self.reinit_count += 1
            self._apply()
        elif self._clock() - self._verified_at >= self._verify_interval_s:
            if self._read16(IODIR) != self.iodir:
                log.warning("MCP23017 0x%02x: registers lost (chip reset?) — re-applying", self.address)
                self.reinit_count += 1
                self._apply()
            self._verified_at = self._clock()

    def _guard(self, fn):
        try:
            self._ensure()
            return fn()
        except OSError:
            self._dirty = True  # re-apply everything on the next successful access
            self._cache = None
            raise

    def _configure(self) -> None:
        """Push the shadow registers now; if the chip is unreachable, keep them
        and apply on the first successful access (absent chip ≠ dead daemon)."""
        self._dirty = True
        try:
            self._guard(lambda: None)
        except OSError as exc:
            log.error("MCP23017 0x%02x unreachable (%s); will configure when it answers", self.address, exc)

    # -- pin API ----------------------------------------------------------
    def setup_output(self, pin: int, level: bool) -> None:
        with self._lock:
            bit = 1 << pin
            self.olat = (self.olat | bit) if level else (self.olat & ~bit)
            self.iodir &= ~bit
            self.gppu &= ~bit
            self._configure()

    def setup_input(self, pin: int, pull: Optional[str]) -> None:
        if pull not in (None, "up", "off", "none"):
            raise ValueError(f"MCP23017 0x{self.address:02x} pin {pin}: only pull 'up' is supported (got {pull!r})")
        with self._lock:
            bit = 1 << pin
            self.iodir |= bit
            self.gppu = (self.gppu | bit) if pull == "up" else (self.gppu & ~bit)
            self._configure()

    def write(self, pin: int, level: bool) -> None:
        """Raises ``OSError`` on an I2C error; the latch keeps its previous value."""
        with self._lock:
            bit = 1 << pin
            new = (self.olat | bit) if level else (self.olat & ~bit)
            self._guard(lambda: self._write16(OLAT, new))
            self.olat = new

    def check(self) -> bool:
        """Periodic health check (re-applies registers after a reset or an
        outage). Returns True when the chip answered."""
        with self._lock:
            try:
                self._guard(lambda: None)
                return True
            except OSError:
                return False

    def read(self, pin: int) -> bool:
        with self._lock:
            now = self._clock()
            if self._cache is None or now - self._cache_at >= self._read_cache_s:
                self._cache = self._guard(lambda: self._read16(GPIO))
                self._cache_at = now
            return bool(self._cache & (1 << pin))

    def release(self) -> None:
        """Shutdown: every pin back to an input, pull-ups off, latches low
        (the power-on state, like ``RPi.GPIO.cleanup()`` for native pins)."""
        with self._lock:
            self.iodir, self.gppu, self.olat = 0xFFFF, 0x0000, 0x0000
            try:
                self._write16(IODIR, self.iodir)
                self._write16(GPPU, self.gppu)
                self._write16(OLAT, self.olat)
            except OSError:
                log.warning("MCP23017 0x%02x: release failed", self.address, exc_info=True)


class FakeMcp23017Bus:
    """In-memory register model of MCP23017 chips (``--mock-gpio`` and tests).

    ``set_input(addr, pin, level)`` drives an external level onto an input;
    ``reset(addr)`` simulates a brown-out; ``fail`` makes every access NACK.
    """

    def __init__(self, addresses: Iterable[int] = ()) -> None:
        self.regs: Dict[int, bytearray] = {}
        self.external: Dict[int, Dict[int, bool]] = {}
        self.fail = False
        self.transactions = 0
        for a in addresses:
            self.add_chip(a)

    def add_chip(self, address: int) -> None:
        self.regs[address] = bytearray(0x16)
        self.reset(address)

    def reset(self, address: int) -> None:
        r = self.regs[address]
        r[:] = bytes(0x16)
        r[0x00] = r[0x01] = 0xFF  # IODIR
        self.external[address] = {}

    def set_input(self, address: int, pin: int, level: Optional[bool]) -> None:
        """Drive an input externally (``None`` = released: reads the pull-up)."""
        if level is None:
            self.external[address].pop(pin, None)
        else:
            self.external[address][pin] = bool(level)

    def reg16(self, address: int, reg: int) -> int:
        r = self.regs[address]
        return r[reg] | (r[reg + 1] << 8)

    def pin_level(self, address: int, pin: int) -> bool:
        """What the pin is driven to (outputs) or reads as (inputs)."""
        return bool(self._gpio(address) & (1 << pin))

    def _gpio(self, address: int) -> int:
        iodir, olat, gppu = (self.reg16(address, x) for x in (IODIR, OLAT, GPPU))
        value = olat & ~iodir & 0xFFFF
        for pin in range(16):
            bit = 1 << pin
            if iodir & bit:
                level = self.external[address].get(pin, bool(gppu & bit))
                value |= bit if level else 0
        return value

    def _check(self, address: int) -> None:
        self.transactions += 1
        if self.fail or address not in self.regs:
            raise OSError(121, "Remote I/O error")

    def write(self, address: int, data: Sequence[int]) -> None:
        self._check(address)
        reg, payload = data[0], list(data[1:])
        for i, b in enumerate(payload):
            target = reg + i
            if target in (GPIO, GPIO + 1):  # writing GPIO writes OLAT
                target += 2
            self.regs[address][target] = b & 0xFF

    def read(self, address: int, length: int) -> bytes:
        raise NotImplementedError

    def write_read(self, address: int, data: Sequence[int], length: int) -> bytes:
        self._check(address)
        reg = data[0]
        if reg == GPIO and length == 2:
            v = self._gpio(address)
            return bytes([v & 0xFF, v >> 8])
        return bytes(self.regs[address][reg:reg + length])


class ExpanderBackend(GpioBackend):
    """Native backend + MCP23017 chips behind one ``GpioBackend``."""

    def __init__(self, native: GpioBackend, chips: Dict[int, Mcp23017], *, watchdog_s: float = 5.0) -> None:
        self.native = native
        self.chips = chips
        self.name = f"{native.name}+mcp23017"
        self._stop = threading.Event()
        self._watchdog: Optional[threading.Thread] = None
        if watchdog_s > 0:
            self._watchdog = threading.Thread(target=self._watch, args=(watchdog_s,),
                                              name="mqttpi-mcp23017", daemon=True)
            self._watchdog.start()

    def _watch(self, every_s: float) -> None:
        # Output-only banks never read, so a chip reset (all relays released)
        # would go unnoticed without this.
        down: set = set()
        while not self._stop.wait(every_s):
            for addr, chip in self.chips.items():
                ok = chip.check()
                if not ok and addr not in down:
                    log.warning("MCP23017 0x%02x not answering", addr)
                    down.add(addr)
                elif ok and addr in down:
                    log.info("MCP23017 0x%02x answering again; outputs restored", addr)
                    down.discard(addr)

    def _chip(self, ref: ExpanderPin) -> Mcp23017:
        try:
            return self.chips[ref.chip]
        except KeyError:
            raise ValueError(f"pin {ref}: no MCP23017 configured at 0x{ref.chip:02x}") from None

    def setup_output(self, pin: PinRef, initial: bool) -> None:
        if isinstance(pin, ExpanderPin):
            return self._chip(pin).setup_output(pin.pin, initial)
        self.native.setup_output(pin, initial)

    def setup_input(self, pin: PinRef, pull: Optional[str]) -> None:
        if isinstance(pin, ExpanderPin):
            return self._chip(pin).setup_input(pin.pin, pull)
        self.native.setup_input(pin, pull)

    def write(self, pin: PinRef, value: bool) -> None:
        if isinstance(pin, ExpanderPin):
            return self._chip(pin).write(pin.pin, value)
        self.native.write(pin, value)

    def read(self, pin: PinRef) -> bool:
        if isinstance(pin, ExpanderPin):
            return self._chip(pin).read(pin.pin)
        return self.native.read(pin)

    def open_pwm(self, pin: PinRef, frequency_hz: float, duty: float = 0.0, **options: Any) -> PwmChannel:
        if isinstance(pin, ExpanderPin):
            raise ValueError(f"pin {pin}: PWM is not available on MCP23017 pins")
        return self.native.open_pwm(pin, frequency_hz, duty, **options)

    def cleanup(self) -> None:
        self._stop.set()
        if self._watchdog is not None:
            self._watchdog.join(timeout=2)
        for chip in self.chips.values():
            chip.release()
        self.native.cleanup()


def expander_chips(cfg: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    """``expanders.mcp23017.chips[]`` keyed by address (enabled section only)."""
    from mqttpi.sensors.i2c import parse_address

    section = ((cfg.get("expanders") or {}).get("mcp23017") or {})
    if not section or not section.get("enabled", True):
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    for i, chip in enumerate(section.get("chips") or []):
        addr = parse_address(chip.get("address"), 0x20 + i)
        if addr in out:
            raise ValueError(f"expanders.mcp23017: address 0x{addr:02x} listed twice")
        out[addr] = dict(chip, bus=int(chip.get("bus", section.get("bus", 1))))
    return out


def build_expander_backend(cfg: Dict[str, Any], native: GpioBackend, *, mock: bool,
                           bus_factory=None, watchdog_s: Optional[float] = None) -> GpioBackend:
    """Wrap ``native`` when the config has expander chips; otherwise return it."""
    chips_cfg = expander_chips(cfg)
    if not chips_cfg:
        return native
    if bus_factory is None:
        if mock:
            fakes: Dict[int, FakeMcp23017Bus] = {}

            def bus_factory(n: int) -> I2cBus:
                return fakes.setdefault(n, FakeMcp23017Bus())
        else:
            from mqttpi.sensors.i2c import open_bus as bus_factory
    chips: Dict[int, Mcp23017] = {}
    for addr, chip_cfg in chips_cfg.items():
        bus = bus_factory(chip_cfg["bus"])
        if isinstance(bus, FakeMcp23017Bus) and addr not in bus.regs:
            bus.add_chip(addr)
        chips[addr] = Mcp23017(bus, addr)
        reset_pin = chip_cfg.get("reset_pin")
        if reset_pin is not None:
            native.setup_output(int(reset_pin), True)  # RESET is active low: hold released
    log.info("MCP23017 expanders: %s", ", ".join(f"0x{a:02x} (bus {c['bus']})" for a, c in chips_cfg.items()))
    section = (cfg.get("expanders") or {}).get("mcp23017") or {}
    if watchdog_s is None:
        watchdog_s = float(section.get("check_interval_s", 5.0))
    return ExpanderBackend(native, chips, watchdog_s=watchdog_s)
