# Plan: Baseline test suite and CI for mqttpi

- **Value:** high
- **Priority:** P2
- **Slug:** test-suite
- **Preferred models:** small, coding-agent
- **Assignee:** ai
- **Depends on:** mqtt-availability-lwt

## Progress
- [ ] Step 1: Unit tests for config loading and pin parsing
- [ ] Step 2: Unit tests for GPIO manager and HA discovery payloads
- [ ] Step 3: Unit tests for the JBD BMS protocol parser
- [ ] Step 4: Daemon smoke test with the mock backend
- [ ] Step 5: CI workflow
- [ ] Done when holds

## Goal
Every push runs a fast, hardware-free test suite covering config loading, pin parsing, the GPIO manager, HA discovery payloads, the JBD protocol parser, and a daemon smoke run, so contributors and downstream users can change mqttpi with confidence.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `mqttpi/config.py`, `mqttpi/gpio/pins.py`, `mqttpi/gpio/manager.py`, `mqttpi/gpio/ha_mqtt.py`, `mqttpi/bms/jbd_protocol.py`, `mqttpi/daemon.py`, `examples/*.yaml` (implemented features only), `.github/workflows/pages.yml` (only existing workflow).
- The harness (fake MQTT client, `pytest.ini`, `requirements-dev.txt`) comes from `mqtt-availability-lwt`.

## Depends on (detail)
- `mqtt-availability-lwt` — extends the minimal pytest harness (`requirements-dev.txt`, `pytest.ini`, `tests/conftest.py` with a fake paho client) created there.

## Constraints
- No hardware, network, or broker needed for the unit suite; broker-based integration tests stay in a separate, optional CI job.
- Tests cover current behavior only; no feature changes in this plan.
- Keep the suite under ~30 s.
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python per `.anchor/conventions.md`: small composable classes, Protocols or narrow ABCs, dependency injection over globals; pytest for tests; user-facing changes documented in `README.md`/`daemon.md`/`config.example.md` and `CHANGELOG.md` `[Unreleased]` when they ship.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | Config tests: secrets deep-merge, defaults, error messages | `tests/test_config.py` | `pytest tests/test_config.py` | small |
| 2 | Pin parsing and GPIO manager tests with `MockGpioBackend`: outputs, inputs with pull, invert, debounce | `tests/test_pins.py`, `tests/test_gpio_manager.py` | `pytest` | small |
| 3 | Discovery payload snapshot tests for switch and binary_sensor, and BMS sensors | `tests/test_discovery.py`, `tests/snapshots/` | `pytest` | small |
| 4 | JBD protocol tests from captured frames: checksum, hwinfo, cellinfo parsing | `tests/test_jbd_protocol.py`, `tests/data/` | `pytest` | small |
| 5 | Daemon smoke test with mock GPIO and the fake client; validate implemented example configs load | `tests/test_daemon_smoke.py` | `pytest` | small |
| 6 | CI workflow running ruff and pytest on pushes and pull requests (oldest supported Python and 3.11) | `.github/workflows/tests.yml` | Workflow green on a branch | small |

## Risks
- Snapshot tests freezing accidental behavior. Mitigation: review snapshots once with the owner.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes locally and in the new CI workflow
- Coverage report shows every module under `mqttpi/` exercised
- No hardware or broker needed for the unit suite
