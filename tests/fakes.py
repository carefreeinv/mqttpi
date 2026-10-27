"""Test doubles shared across the mqttpi test suite (no broker, no hardware)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass
class Published:
    topic: str
    payload: str
    qos: int
    retain: bool


class FakeReasonCode:
    def __init__(self, value: int = 0) -> None:
        self.value = value
        self.is_failure = value != 0

    def __str__(self) -> str:  # pragma: no cover - log formatting only
        return "Success" if not self.is_failure else f"Failure({self.value})"


@dataclass
class FakePahoClient:
    """Records every call the code under test makes on a paho ``Client``."""

    client_id: str = ""
    calls: List[Tuple[str, tuple, dict]] = field(default_factory=list)
    published: List[Published] = field(default_factory=list)
    subscriptions: List[Tuple[str, int]] = field(default_factory=list)
    will: Optional[Published] = None
    loop_running: bool = False
    connect_error: Optional[BaseException] = None
    on_connect: Any = None
    on_disconnect: Any = None
    on_message: Any = None

    # -- paho API surface used by mqttpi ------------------------------
    def username_pw_set(self, username: str, password: Optional[str] = None) -> None:
        self.calls.append(("username_pw_set", (username, password), {}))

    def will_set(self, topic: str, payload: Any = None, qos: int = 0, retain: bool = False) -> None:
        self.calls.append(("will_set", (topic, payload), {"qos": qos, "retain": retain}))
        self.will = Published(topic, str(payload), qos, retain)

    def connect(self, host: str, port: int = 1883, keepalive: int = 60, **kwargs: Any) -> int:
        self.calls.append(("connect", (host, port), {"keepalive": keepalive, **kwargs}))
        if self.connect_error is not None:
            raise self.connect_error
        return 0

    def connect_async(self, host: str, port: int = 1883, keepalive: int = 60, **kwargs: Any) -> None:
        self.calls.append(("connect_async", (host, port), {"keepalive": keepalive, **kwargs}))

    def reconnect_delay_set(self, min_delay: int = 1, max_delay: int = 120) -> None:
        self.calls.append(("reconnect_delay_set", (min_delay, max_delay), {}))

    def max_queued_messages_set(self, queue_size: int) -> None:
        self.calls.append(("max_queued_messages_set", (queue_size,), {}))

    def tls_set(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("tls_set", args, kwargs))

    def tls_insecure_set(self, value: bool) -> None:
        self.calls.append(("tls_insecure_set", (value,), {}))

    def loop_start(self) -> None:
        self.calls.append(("loop_start", (), {}))
        self.loop_running = True

    def loop_stop(self) -> None:
        self.calls.append(("loop_stop", (), {}))
        self.loop_running = False

    def disconnect(self) -> None:
        self.calls.append(("disconnect", (), {}))

    def subscribe(self, topic: str, qos: int = 0) -> Tuple[int, int]:
        self.calls.append(("subscribe", (topic,), {"qos": qos}))
        self.subscriptions.append((topic, qos))
        return (0, len(self.subscriptions))

    def publish(self, topic: str, payload: Any = None, qos: int = 0, retain: bool = False) -> Any:
        self.calls.append(("publish", (topic, payload), {"qos": qos, "retain": retain}))
        self.published.append(Published(topic, "" if payload is None else str(payload), qos, retain))
        return None

    # -- helpers for tests ---------------------------------------------
    def call_names(self) -> List[str]:
        return [name for name, _a, _k in self.calls]

    def simulate_connect(self, rc: int = 0) -> None:
        assert self.on_connect is not None, "on_connect not registered"
        self.on_connect(self, None, {}, FakeReasonCode(rc), None)

    def simulate_disconnect(self, rc: int = 7) -> None:
        if self.on_disconnect is not None:
            self.on_disconnect(self, None, {}, FakeReasonCode(rc), None)

    def simulate_message(self, topic: str, payload: str) -> None:
        assert self.on_message is not None

        class _Msg:
            pass

        msg = _Msg()
        msg.topic = topic  # type: ignore[attr-defined]
        msg.payload = payload.encode("utf-8")  # type: ignore[attr-defined]
        self.on_message(self, None, msg)

    def published_to(self, topic: str) -> List[Published]:
        return [p for p in self.published if p.topic == topic]

    def last_payload(self, topic: str) -> Optional[str]:
        items = self.published_to(topic)
        return items[-1].payload if items else None
