"""Command filter hook: inspect, modify, or reject output commands.

Every request to change a GPIO output (an MQTT ``…/gpio/{alias}/set`` message
or a call to :meth:`GpioManager.request_output`) is turned into a
:class:`CommandRequest` and passed through the registered filters, in
registration order, before anything is written to hardware.

* A filter returns ``None`` or :meth:`CommandDecision.accept` to let the
  command through unchanged.
* :meth:`CommandDecision.modify` replaces the requested value; later filters
  see the modified value.
* :meth:`CommandDecision.reject` stops the command. The first reject wins and
  the remaining filters are not called.
* A filter that raises is treated as a reject (fail safe) and the exception
  is logged.

After a rejected or modified command the manager publishes the *actual*
output state so Home Assistant never shows a state the hardware is not in.

Threading: filters run on the MQTT network thread (or the caller's thread for
``request_output``). They must be fast and non-blocking — no network calls,
no sleeps. A filter taking longer than :data:`SLOW_FILTER_WARN_S` is logged.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, List, Mapping, Optional, Protocol, Sequence, Tuple

log = logging.getLogger(__name__)

SLOW_FILTER_WARN_S = 0.05

ACCEPT = "accept"
MODIFY = "modify"
REJECT = "reject"


@dataclass(frozen=True)
class CommandRequest:
    """An incoming request to set an output."""

    alias: str
    value: Any  # bool for digital outputs
    current: Any  # value the output has right now
    source: str  # MQTT topic, or "api" for request_output()
    payload: Optional[str] = None  # raw MQTT payload, if any
    states: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    """Read-only snapshot of every output and input state, keyed by alias."""


@dataclass(frozen=True)
class CommandDecision:
    action: str
    value: Any = None
    reason: str = ""

    @classmethod
    def accept(cls) -> "CommandDecision":
        return cls(ACCEPT)

    @classmethod
    def modify(cls, value: Any, reason: str = "") -> "CommandDecision":
        return cls(MODIFY, value, reason)

    @classmethod
    def reject(cls, reason: str) -> "CommandDecision":
        return cls(REJECT, None, reason)

    @property
    def rejected(self) -> bool:
        return self.action == REJECT


class CommandFilter(Protocol):
    def __call__(self, request: CommandRequest) -> Optional[CommandDecision]: ...


@dataclass(frozen=True)
class FilterOutcome:
    """Result of running a request through the whole filter chain."""

    accepted: bool
    value: Any
    reasons: Tuple[str, ...] = ()

    def changed_from(self, requested: Any) -> bool:
        return not self.accepted or self.value != requested


def _name(f: Any) -> str:
    return getattr(f, "__name__", None) or type(f).__name__


def run_filters(filters: Sequence[CommandFilter], request: CommandRequest) -> FilterOutcome:
    """Apply ``filters`` in order. First reject wins; modifies chain."""
    value = request.value
    reasons: List[str] = []
    for f in filters:
        req = request if value == request.value else _with_value(request, value)
        started = time.monotonic()
        try:
            decision = f(req)
        except Exception:  # noqa: BLE001 — a broken filter must fail safe
            log.exception("Command filter %s raised; rejecting %s", _name(f), request.alias)
            return FilterOutcome(False, request.current, tuple(reasons) + (f"filter {_name(f)} raised",))
        finally:
            elapsed = time.monotonic() - started
            if elapsed > SLOW_FILTER_WARN_S:
                log.warning(
                    "Command filter %s took %.0f ms; filters must be fast and non-blocking",
                    _name(f),
                    elapsed * 1000,
                )
        if decision is None or decision.action == ACCEPT:
            continue
        if decision.action == REJECT:
            reasons.append(decision.reason or _name(f))
            return FilterOutcome(False, request.current, tuple(reasons))
        if decision.action == MODIFY:
            value = decision.value
            if decision.reason:
                reasons.append(decision.reason)
            continue
        log.error("Command filter %s returned unknown action %r; rejecting", _name(f), decision.action)
        return FilterOutcome(False, request.current, tuple(reasons) + ("invalid filter decision",))
    return FilterOutcome(True, value, tuple(reasons))


def _with_value(request: CommandRequest, value: Any) -> CommandRequest:
    return CommandRequest(
        alias=request.alias,
        value=value,
        current=request.current,
        source=request.source,
        payload=request.payload,
        states=request.states,
    )


# --- Ready-made filters -------------------------------------------------------


def mutually_exclusive(*aliases: str) -> CommandFilter:
    """Never allow more than one of ``aliases`` to be ON at the same time.

    Typical use: the two direction relays of a reversible motor or linear
    actuator (extend / retract), where both ON would short the supply. Turning
    one ON while another is ON is rejected — switch the active one OFF first.
    """
    group = frozenset(aliases)
    if len(group) < 2:
        raise ValueError("mutually_exclusive needs at least two aliases")

    def mutually_exclusive_filter(req: CommandRequest) -> Optional[CommandDecision]:
        if req.alias not in group or not req.value:
            return None
        others_on = sorted(a for a in group if a != req.alias and req.states.get(a))
        if others_on:
            return CommandDecision.reject(
                f"{req.alias} blocked: interlocked with {', '.join(others_on)} (ON)"
            )
        return None

    return mutually_exclusive_filter


def block_while(alias: str, input_alias: str, active: bool = True) -> CommandFilter:
    """Reject turning ``alias`` ON while ``input_alias`` is ``active``.

    Example: keep an actuator from extending while its end-stop input is hit.
    Turning the output OFF is always allowed.
    """

    def block_while_filter(req: CommandRequest) -> Optional[CommandDecision]:
        if req.alias != alias or not req.value:
            return None
        if bool(req.states.get(input_alias)) == active:
            return CommandDecision.reject(
                f"{alias} blocked while {input_alias} is {'ON' if active else 'OFF'}"
            )
        return None

    return block_while_filter



def clamp_duty(alias: str, low: float = 0.0, high: float = 100.0) -> CommandFilter:
    """Limit a ``pwm_output`` duty to ``low``..``high`` percent (0 always passes).

    Example: cap a motor driver at 80 % or keep a fan above its stall speed.
    """
    if not 0 <= low <= high <= 100:
        raise ValueError("clamp_duty needs 0 <= low <= high <= 100")

    def clamp_duty_filter(req: CommandRequest) -> Optional[CommandDecision]:
        if req.alias != alias or not req.value:
            return None
        value = float(req.value)
        clamped = min(high, max(low, value))
        if clamped != value:
            return CommandDecision.modify(clamped, f"{alias} duty clamped to {low:g}-{high:g} %")
        return None

    return clamp_duty_filter
