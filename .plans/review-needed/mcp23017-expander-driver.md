# Plan: MCP23017 I2C pin expander driver

- **Value:** medium
- **Priority:** P3
- **Slug:** mcp23017-expander-driver
- **Preferred models:** mid, coding-agent
- **Assignee:** ai
- **Depends on:** command-filter-hook

## Progress
- [x] Step 1: Expander backend implementing the GPIO backend interface
- [x] Step 2: Config wiring for expander pins
- [ ] Step 3: Docs and bench test
- [ ] Done when holds

## Goal
Pins on MCP23017 expanders (as already described in the config contract and relay-bank examples) work as normal mqttpi inputs and outputs, with the same HA entities, topics, and command filtering as native GPIO.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `examples/relay-bank-16.yaml`, `examples/relay-bank-32.yaml`, `CHANGELOG.md` (v0.1.1 MCP23017 config fix), `mqttpi/gpio/backend.py`, `mqttpi/gpio/pins.py`.

## Depends on (detail)
- `command-filter-hook` — expander outputs must go through the same command path; lands after the GPIO manager refactor.

## Constraints
- Implements the existing `GpioBackend` interface; manager code stays backend-agnostic.
- Interrupt pins optional; polling acceptable with documented latency.
- `smbus2` as the optional extra shared with I2C sensors.
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python per `.anchor/conventions.md`: small composable classes, Protocols or narrow ABCs, dependency injection over globals; pytest for tests; user-facing changes documented in `README.md`/`daemon.md`/`config.example.md` and `CHANGELOG.md` `[Unreleased]` when they ship.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | `Mcp23017Backend` over `smbus2` with a fake register map in tests | `mqttpi/gpio/mcp23017.py`, tests | Unit tests | mid |
| 2 | Resolve pins addressed to an expander in config to the right backend | `mqttpi/gpio/pins.py`, `mqttpi/gpio/manager.py`, tests | `examples/relay-bank-16.yaml` loads and runs with the fake | mid |
| 3 | Docs, changelog, bench test with a real expander | `daemon.md`, `CHANGELOG.md` | Bench result recorded | human |

## Risks
- Expander reset leaves outputs in power-on state. Mitigation: re-apply output state after I2C errors; document default polarity.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes
- Relay-bank examples run with the fake expander
- Bench result recorded

## Handoff

- Implemented on `feature/mcp23017-expander-driver`, stacked on `feature/onewire-i2c-sensor-drivers`, which provides the shared I2C bus and the `smbus2` extra.
- **Steps 1–2 are done**, with unit tests against an in-memory register model.
  - The relay-bank-32 example runs with the fake. relay-bank-16 is unchanged.
- **Step 3:** the docs are done. The **bench test is open**:
  - two MCP23017 chips at 0x20/0x21 on a Pi;
  - relay toggles from HA;
  - an input with a pull-up;
  - power-cycle one chip while running and confirm its outputs are restored within `check_interval_s`;
  - unplug SDA and confirm the daemon keeps running and recovers.
- **Decision:** expander pins are released to inputs on shutdown, matching `RPi.GPIO.cleanup()`.
