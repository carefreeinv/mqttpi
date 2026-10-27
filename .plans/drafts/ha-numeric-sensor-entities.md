# Plan: Home Assistant numeric sensor entity support (shared base for sensor drivers)

- **Value:** high
- **Priority:** P2
- **Slug:** ha-numeric-sensor-entities
- **Preferred models:** mid, coding-agent
- **Assignee:** ai
- **Depends on:** mqtt-availability-lwt

## Progress
- [ ] Step 1: Generic numeric sensor publisher with discovery
- [ ] Step 2: Sensor driver interface and polling scheduler
- [ ] Step 3: Wire into the daemon
- [ ] Step 4: Docs
- [ ] Done when holds

## Goal
mqttpi has one generic way to publish numeric readings as Home Assistant `sensor` entities (state topic, unit, device_class, state_class, availability), plus a small driver interface and polling scheduler, so every sensor driver (1-Wire, I2C, ADC, CAN-derived values) reuses it instead of each inventing topics.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `mqttpi/gpio/ha_mqtt.py` (switch and binary_sensor only), `mqttpi/bms/ha_mqtt.py` (an existing numeric sensor publisher to generalize from), `examples/sensors-i2c-onewire.yaml`, `examples/analog-inputs.yaml` (documented topics `{base_topic}/<subsystem>/<alias>/state`).

## Depends on (detail)
- `mqtt-availability-lwt` — reuses the pytest harness and correct availability semantics.

## Constraints
- Topic layout follows the documented examples: `{base_topic}/sensor/<alias>/state` (or the subsystem names already used in `examples/`; pick one and document it).
- Readings carry a timestamp and a quality flag; failed reads publish nothing and mark the entity unavailable after a configurable staleness.
- Poll intervals per sensor; one scheduler thread; a slow driver cannot stall others (timeouts).
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python Protocol `SensorDriver` with `read() -> Reading`; registry keyed by config `type`; composition over inheritance.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | `NumericSensorPublisher`: discovery config (unit, device_class, state_class), state publish, per-entity availability | `mqttpi/sensors/ha_mqtt.py`, tests | Discovery snapshot tests | mid |
| 2 | `SensorDriver` Protocol, `Reading` type, registry, and polling scheduler with timeouts; a fake driver for tests | `mqttpi/sensors/`, tests | Unit tests: scheduling, timeout, staleness | mid |
| 3 | Daemon enables the sensor subsystem when `sensors[]` (or the documented key) is present | `mqttpi/daemon.py`, tests | Smoke test with the fake driver | small |
| 4 | Document the sensor subsystem and topics | `daemon.md`, `config.example.md`, `CHANGELOG.md` | Docs build passes | small |

## Risks
- Diverging from config contracts already documented in `examples/`. Mitigation: Step 1 reads them and keeps their keys.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes
- A fake sensor appears in Home Assistant discovery format with unit and device class (snapshot)
- Docs and changelog updated
