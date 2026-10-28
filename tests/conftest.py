"""Shared fixtures: a fake paho client factory so no broker is needed."""

from __future__ import annotations

from typing import Any, List

import paho.mqtt.client as paho
import pytest

from tests.fakes import FakePahoClient


class FakeClientFactory:
    def __init__(self) -> None:
        self.instances: List[FakePahoClient] = []

    def __call__(self, *_args: Any, client_id: str = "", **_kwargs: Any) -> FakePahoClient:
        client = FakePahoClient(client_id=client_id)
        self.instances.append(client)
        return client

    @property
    def last(self) -> FakePahoClient:
        assert self.instances, "no paho client was created"
        return self.instances[-1]


@pytest.fixture
def fake_paho(monkeypatch: pytest.MonkeyPatch) -> FakeClientFactory:
    """Replace ``paho.mqtt.client.Client`` everywhere mqttpi constructs one."""
    factory = FakeClientFactory()
    monkeypatch.setattr(paho, "Client", factory)
    return factory
