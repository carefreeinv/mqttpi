# Plan: Implement the existing `mqtt.tls` config key

- **Value:** high
- **Priority:** P1
- **Slug:** mqtt-tls
- **Preferred models:** mid, coding-agent
- **Assignee:** ai
- **Depends on:** mqtt-resilient-connect

## Progress
- [ ] Step 1: Define the TLS config schema
- [ ] Step 2: Wire TLS into `MqttConnection`
- [ ] Step 3: Port defaults and validation
- [ ] Step 4: Docs
- [ ] Step 5: Integration test against a TLS Mosquitto listener
- [ ] Done when holds

## Goal
Setting `mqtt.tls` actually encrypts the broker connection (with CA verification, optional client certificate, optional insecure mode for lab use), so mqttpi can be used on shared or untrusted networks. Today the key is documented in config but ignored.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `config.example.yaml` / `config.example.md` (`mqtt.tls: false`), `mqttpi/mqtt/client.py` (no `tls_set` call), `mqttpi/daemon.py` `build_mqtt`, `secrets.example.yaml`.

## Depends on (detail)
- `mqtt-resilient-connect` — TLS setup sits in the same connect path; land the non-blocking connect first to avoid conflicting edits.

## Constraints
- Backward compatible: `tls: false` (default) unchanged; `tls: true` uses the system CA store; a mapping form allows `ca_certs`, `certfile`, `keyfile`, `insecure` (hostname check off, logged as a warning).
- File paths may live in `secrets.yaml`; never log key material.
- Default port becomes 8883 only when TLS is on and no port is set.
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python per `.anchor/conventions.md`: small composable classes, Protocols or narrow ABCs, dependency injection over globals; pytest for tests; user-facing changes documented in `README.md`/`daemon.md`/`config.example.md` and `CHANGELOG.md` `[Unreleased]` when they ship.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | Specify the `mqtt.tls` schema (bool or mapping) and validation errors | `mqttpi/config.py`, `config.example.md`, tests | Unit tests for valid and invalid configs | small |
| 2 | Call `tls_set` / `tls_insecure_set` in `MqttConnection` from the parsed settings | `mqttpi/mqtt/client.py`, tests | Unit test with the fake client records TLS calls | mid |
| 3 | Port default and logging of the effective transport | `mqttpi/daemon.py`, tests | Unit test | small |
| 4 | Document TLS setup including a Mosquitto example | `daemon.md`, `config.example.md`, `CHANGELOG.md` | Docs build passes | small |
| 5 | Integration test: Mosquitto with a test CA on 8883; connect with CA, fail with wrong CA | `tests/integration/test_tls.py`, test certs generated at test time | Integration test passes | mid |

## Risks
- Certificate expiry on unattended devices. Mitigation: log certificate errors clearly; document renewal.
- Clock not set at boot on boards without an RTC makes certificate validation fail. Mitigation: document; retries from `mqtt-resilient-connect` recover once time syncs.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes
- TLS integration test passes (good CA connects, wrong CA refused)
- `tls: false` behavior unchanged (regression test)
- Docs and changelog updated
