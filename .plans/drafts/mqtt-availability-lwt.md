# Plan: Last Will so `{base_topic}/status` goes `offline` when a node dies

- **Value:** high
- **Priority:** P1
- **Slug:** mqtt-availability-lwt
- **Preferred models:** mid, coding-agent
- **Assignee:** ai
- **Depends on:** none

## Progress
- [ ] Step 1: Bootstrap a minimal pytest harness with a fake MQTT client
- [ ] Step 2: Set the Last Will in `MqttConnection` before connecting
- [ ] Step 3: Publish `online` again on every (re)connect
- [ ] Step 4: Daemon wiring and docs
- [ ] Step 5: Broker test: kill -9 yields retained `offline`
- [ ] Done when holds

## Goal
When an mqttpi process crashes, loses power, or drops off the network, the broker publishes the retained availability message `offline` on `{base_topic}/status`, so Home Assistant and any downstream consumer stop trusting stale state. Today `offline` is only published on a clean shutdown, so a dead node stays retained `online` indefinitely.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `mqttpi/mqtt/client.py` (`MqttConnection.__init__`, `connect`, `publish_availability`), `mqttpi/daemon.py` (`Daemon.run` publishes `online` after connect; `shutdown` publishes `offline`), `mqttpi/gpio/ha_mqtt.py` (discovery `availability_topic`), `mqttpi/bms/ha_mqtt.py` (separate client, `publish_offline`).
- paho-mqtt 2.x `Client.will_set(topic, payload, qos, retain)` must be called before `connect`.
- No tests exist yet in the repo; this plan is the first to need them, so it creates the minimal harness that later plans reuse (`test-suite` broadens it).

## Constraints
- Will topic and payloads are exactly the existing availability contract: `{base_topic}/status`, `offline`/`online` (honor any configured payload overrides if present), retained, using the configured qos.
- `online` must be re-published after every successful (re)connect, because a broker-side will may have fired during an outage.
- Library users constructing `MqttConnection` directly get the will by default; an explicit constructor argument may disable it.
- The BMS publisher's own connection is out of scope (see `bms-shared-connection`) except that it must not publish a conflicting will on the same topic.
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python per `.anchor/conventions.md`: small composable classes, Protocols or narrow ABCs, dependency injection over globals; pytest for tests; user-facing changes documented in `README.md`/`daemon.md`/`config.example.md` and `CHANGELOG.md` `[Unreleased]` when they ship.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | Create `requirements-dev.txt` (pytest), `pytest.ini`, and `tests/conftest.py` with a fake paho client that records `will_set`, `publish`, `subscribe`, and connect callbacks | `requirements-dev.txt`, `pytest.ini`, `tests/conftest.py` | `pytest -q` runs (zero or more tests) in a clean venv | small |
| 2 | `MqttConnection` takes `availability_topic` (derived from `base_topic`) and calls `will_set(..., 'offline', qos, retain=True)` before connecting | `mqttpi/mqtt/client.py`, `tests/test_mqtt_client.py` | Unit test: will set before connect with correct topic, payload, qos, retain | mid |
| 3 | Publish `online` from paho's `on_connect` callback on every successful connect instead of once in `Daemon.run` | `mqttpi/mqtt/client.py`, `mqttpi/daemon.py`, tests | Unit test: two simulated connects produce two retained `online` publishes | mid |
| 4 | Document the availability behavior and the library constructor option | `daemon.md`, `README.md` (MQTT topics), `CHANGELOG.md` `[Unreleased]` | Docs build: `python3 scripts/stage_docs.py && mkdocs build` | small |
| 5 | Integration test against a local Mosquitto (container or CI service): start the daemon with `--mock-gpio`, `kill -9` it, observe retained `offline` | `tests/integration/test_availability.py`, CI job | Integration test passes locally or in CI | mid |

## Risks
- Keepalive too long delays the will. Mitigation: document `mqtt.keepalive` (add the key if missing, default unchanged) and its effect on detection time.
- Retained `offline` from an old session overwriting a fresh `online`. Mitigation: publish `online` from `on_connect` after the session is established.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes, including will and reconnect tests
- Integration test shows retained `offline` after an abrupt kill and `online` after restart
- Docs and `CHANGELOG.md` `[Unreleased]` updated; docs build passes
