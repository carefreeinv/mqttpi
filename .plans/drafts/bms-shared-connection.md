# Plan: BMS subsystem shares the daemon's single MQTT connection

- **Value:** medium
- **Priority:** P2
- **Slug:** bms-shared-connection
- **Preferred models:** mid, coding-agent
- **Assignee:** ai
- **Depends on:** mqtt-resilient-connect

## Progress
- [ ] Step 1: Let `BmsMqttPublisher` publish through an injected `MqttConnection`
- [ ] Step 2: Daemon passes its connection to the BMS subsystem
- [ ] Step 3: Keep the standalone bridge working
- [ ] Step 4: Tests and docs
- [ ] Done when holds

## Goal
When the unified daemon runs GPIO and BMS together it uses one MQTT connection (one client id, one will, one availability topic) instead of two, and the standalone `mqttpi-bms` bridge keeps working.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `mqttpi/bms/subsystem.py` (`BmsSubsystem` builds its own publisher via `bridge.build_publisher` and calls its `connect`), `mqttpi/bms/ha_mqtt.py` (`BmsMqttPublisher` owns a paho client), `mqttpi/bms/bridge.py` (standalone entry point, `mqttpi-bms.service`), `mqttpi/daemon.py`.

## Depends on (detail)
- `mqtt-resilient-connect` — the shared connection must already be non-blocking and re-announce on reconnect; the will from `mqtt-availability-lwt` comes with it.

## Constraints
- Topics, discovery payloads, and availability semantics for BMS entities do not change (or change only in a documented, backward-compatible way).
- Standalone `python3 -m mqttpi.bms.bridge` still works with its own connection.
- Client ids must not collide when both the standalone bridge and the daemon run.
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python per `.anchor/conventions.md`: small composable classes, Protocols or narrow ABCs, dependency injection over globals; pytest for tests; user-facing changes documented in `README.md`/`daemon.md`/`config.example.md` and `CHANGELOG.md` `[Unreleased]` when they ship.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | Refactor `BmsMqttPublisher` to depend on a small publish interface implemented by `MqttConnection` | `mqttpi/bms/ha_mqtt.py`, `mqttpi/mqtt/client.py`, tests | Unit tests with the fake client | mid |
| 2 | `Daemon` passes its connection into `BmsSubsystem`; remove the second connect in daemon mode | `mqttpi/bms/subsystem.py`, `mqttpi/daemon.py`, tests | Unit test: one client created in daemon mode | mid |
| 3 | Standalone bridge builds its own `MqttConnection` (gaining will and reconnect) | `mqttpi/bms/bridge.py`, tests | Unit test of the bridge entry point | small |
| 4 | Docs and changelog | `daemon.md`, `CHANGELOG.md` | Docs build passes | small |

## Risks
- Existing HA entities change unique ids or availability topics. Mitigation: snapshot tests of discovery payloads before and after.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes, including discovery snapshot tests
- Daemon mode opens exactly one MQTT connection
- Standalone bridge still publishes BMS data
