# Plan: Implement `pwm_output` (Home Assistant number 0–100)

- **Value:** medium
- **Priority:** P3
- **Slug:** pwm-output-driver
- **Preferred models:** mid, coding-agent
- **Assignee:** ai
- **Depends on:** command-filter-hook

## Progress
- [ ] Step 1: PWM backend interface (hardware and software PWM)
- [ ] Step 2: `pwm_output` pin direction with HA number discovery
- [ ] Step 3: Commands through the command filter
- [ ] Step 4: Docs and bench test
- [ ] Done when holds

## Goal
The documented `pwm_output` config contract works: a pin configured as PWM is exposed as a Home Assistant `number` (0–100 %), accepts values on `{base_topic}/gpio/{alias}/set`, and drives hardware PWM where available, with commands passing through the pre-actuation filter.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `examples/pwm-bank.yaml`, `examples/pi4-pwm-relay.yaml`, `config.example.yaml` (`pwm` section, `frequency_hz`), `mqttpi/gpio/backend.py`, `mqttpi/gpio/manager.py`, `mqttpi/gpio/commands.py` (from `command-filter-hook`).

## Depends on (detail)
- `command-filter-hook` — PWM set commands must be filterable and clampable like on/off commands.

## Constraints
- Match the documented config keys and HA number range exactly.
- Hardware PWM preferred; software PWM allowed with a documented accuracy warning.
- Safe initial duty from config (default 0).
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python per `.anchor/conventions.md`: small composable classes, Protocols or narrow ABCs, dependency injection over globals; pytest for tests; user-facing changes documented in `README.md`/`daemon.md`/`config.example.md` and `CHANGELOG.md` `[Unreleased]` when they ship.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | Extend the backend interface with PWM setup and duty; mock implementation | `mqttpi/gpio/backend.py`, tests | Unit tests | mid |
| 2 | Parse `pwm_output` pins; publish HA number discovery and state; handle numeric `/set` | `mqttpi/gpio/pins.py`, `mqttpi/gpio/manager.py`, `mqttpi/gpio/ha_mqtt.py`, tests | Unit tests and discovery snapshot | mid |
| 3 | Route PWM commands through the command filter (clamp example) | `mqttpi/gpio/manager.py`, tests | Unit test | small |
| 4 | Docs, changelog, bench test on a Pi with an LED or fan | `daemon.md`, `CHANGELOG.md` | Docs build passes; bench result recorded | human |

## Risks
- Frequency limits differ per board. Mitigation: validate against board metadata if `pi-zero-w-board` has landed; otherwise document.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes
- `examples/pwm-bank.yaml` runs with `--mock-gpio`
- Bench result recorded
