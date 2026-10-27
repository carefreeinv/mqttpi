# Plan: Pi Zero W (and Zero 2 W) as a supported, documented board

- **Value:** medium
- **Priority:** P2
- **Slug:** pi-zero-w-board
- **Preferred models:** small, human
- **Assignee:** ai
- **Depends on:** gpio-backend-fail-loud

## Progress
- [ ] Step 1: Add the board profile
- [ ] Step 2: Pin map and validation
- [ ] Step 3: Bench test on real hardware
- [ ] Step 4: Docs and example
- [ ] Done when holds

## Goal
`device.board: pizero` (Pi Zero W / Zero 2 W) is a recognized, validated, documented board, with its pin map, hardware PWM pins, and known limits (single core, 2.4 GHz Wi-Fi, no ADC), tested on real hardware.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `config.example.yaml` (`device.board: picow | pi4 | pi5`), `mqttpi/gpio/manager.py` (board only used as the HA model string), `examples/pi4-maximum-gpio.yaml`, `README.md` board table.

## Depends on (detail)
- `gpio-backend-fail-loud` — board support relies on strict GPIO library selection and the declared dependency.

## Constraints
- Same 40-pin BCM numbering as other Pi models; validate reserved pins (I2C, UART, SPI) per board when buses are enabled.
- No board-specific code paths unless needed; profile is data.
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python per `.anchor/conventions.md`: small composable classes, Protocols or narrow ABCs, dependency injection over globals; pytest for tests; user-facing changes documented in `README.md`/`daemon.md`/`config.example.md` and `CHANGELOG.md` `[Unreleased]` when they ship.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | Add board metadata (pin list, hardware PWM pins, ADC: none) and validation of `pins[]` against it | `mqttpi/boards.py`, `mqttpi/gpio/pins.py`, tests | Unit tests: invalid pin rejected for the board | small |
| 2 | Example config and README board table entry | `examples/pizero-relays.yaml`, `examples/pizero-relays.md`, `README.md` | Docs build passes; example loads in tests | small |
| 3 | Bench test on a Pi Zero W with Raspberry Pi OS Lite: outputs, inputs, daemon CPU and memory over 24 h | none (record results in Progress) | Owner sign-off | human |
| 4 | Changelog | `CHANGELOG.md` | Docs build passes | small |

## Risks
- GPIO library support differs by OS release. Mitigation: record the tested OS and library versions.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes with board validation tests
- Bench results recorded and signed off
- Docs list the board with its tested OS
