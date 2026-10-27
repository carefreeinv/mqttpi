# Plan: Start and keep running when the broker is down (non-blocking connect with backoff)

- **Value:** high
- **Priority:** P1
- **Slug:** mqtt-resilient-connect
- **Preferred models:** mid, coding-agent
- **Assignee:** ai
- **Depends on:** mqtt-availability-lwt

## Progress
- [ ] Step 1: Non-blocking first connect with bounded backoff in `MqttConnection`
- [ ] Step 2: Daemon starts subsystems without waiting for the broker
- [ ] Step 3: Publish behavior while disconnected
- [ ] Step 4: Docs
- [ ] Step 5: Integration test: broker down at boot, then up
- [ ] Done when holds

## Goal
`python3 -m mqttpi` and library users of `MqttConnection` start normally when the broker is unreachable, keep local work (GPIO inputs, BMS polling) running, and connect as soon as the broker appears, instead of exiting at startup.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `mqttpi/mqtt/client.py` (`connect()` calls the synchronous `client.connect` then `loop_start`; raises if the broker is down), `mqttpi/bms/ha_mqtt.py` (`BmsMqttPublisher.connect`, same pattern), `mqttpi/daemon.py` (`Daemon.run` connects before starting subsystems), `mqttpi.service` (`Restart=on-failure` currently masks the failure with restart loops).
- paho-mqtt 2.x: `connect_async` plus `loop_start` retries with `reconnect_delay_set(min, max)`.

## Depends on (detail)
- `mqtt-availability-lwt` — the will and `on_connect` re-announce must exist first so a late connect still publishes correct availability; reuses its test harness and fake client.

## Constraints
- Never block the caller's thread waiting for the broker; never raise on an unreachable broker at startup (configuration errors such as an invalid hostname format still fail fast).
- Backoff bounds configurable (`mqtt.reconnect_min_s`, `mqtt.reconnect_max_s`), defaults documented.
- Publishes while disconnected must not raise or block; drop-or-queue behavior is explicit (paho queues qos>0 messages up to `max_queued_messages`; set and document a bound).
- Logs one warning per outage, not one per retry.
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python per `.anchor/conventions.md`: small composable classes, Protocols or narrow ABCs, dependency injection over globals; pytest for tests; user-facing changes documented in `README.md`/`daemon.md`/`config.example.md` and `CHANGELOG.md` `[Unreleased]` when they ship.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | `MqttConnection.connect()` uses `connect_async` + `loop_start` + `reconnect_delay_set`; add `is_connected` and an optional `wait_connected(timeout)` for callers that want it | `mqttpi/mqtt/client.py`, tests | Unit tests with the fake client: no exception when the broker is down; retries scheduled | mid |
| 2 | Daemon starts GPIO and BMS subsystems before the broker is reachable; subscriptions are (re)made in `on_connect` | `mqttpi/daemon.py`, `mqttpi/mqtt/client.py`, tests | Unit test: subscriptions re-issued after reconnect | mid |
| 3 | Bound the offline queue (`max_queued_messages_set`) and make the drop policy explicit | `mqttpi/mqtt/client.py`, tests | Unit test of the configured bound | small |
| 4 | Document startup and reconnect behavior and new keys | `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` | Docs build passes | small |
| 5 | Integration test: start daemon with broker stopped, start broker 30 s later, see `online` and discovery published; restart broker mid-run | `tests/integration/test_reconnect.py` | Integration test passes | mid |

## Risks
- Retained HA discovery configs must be re-published after a broker restart without persistence. Mitigation: publish discovery from `on_connect`.
- Changing startup semantics could hide misconfiguration. Mitigation: log the broker target clearly and warn after N failed attempts.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes
- Integration test: daemon survives broker-down boot and broker restart, and publishes availability and discovery after connecting
- Docs and changelog updated; docs build passes
