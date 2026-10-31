# Plan: Pi Zero W (and Zero 2 W) as a supported, documented board

- **Value:** medium
- **Priority:** P2
- **Slug:** pi-zero-w-board
- **Preferred models:** small, human
- **Assignee:** ai
- **Depends on:** gpio-backend-fail-loud

## Progress
- [x] Step 1: Add the board profile
- [x] Step 2: Pin map and validation
- [ ] Step 3: Bench test on real hardware
- [x] Step 4: Docs and example
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

## Handoff
- Implemented on branch `feature/pi-zero-w-board`, stacked on `fix/input-debounce-and-jbd-frames`.
- Step 1–2 (profile, pin map, validation):
  - `mqttpi/boards.py` adds the `BoardProfile` data for `pi3`, `pi4`, `pi5`, `pizero` and `picow`. Aliases include `pizero2w`, `pizero_w`, `zero2w` and `pico_w`.
  - `validate_pins(cfg)` is called from `GpioManager.__init__`. The validation hook lives in `boards.py` rather than `gpio/pins.py`, so `parse_pins` stays board-agnostic.
  - Hard errors, all listed together, stop startup: a pin that does not exist on the board, a duplicate pin, or a pin claimed by an enabled bus (any integer setting under an enabled `buses.*`, or GPIO 14/15 when `bms.port` is `/dev/serial0`).
  - Warnings: GPIO 0/1 (ID EEPROM), `analog` without an ADC, and `pwm` without hardware PWM.
  - A missing or unknown `device.board` is not validated, so the change is backward compatible. Every example YAML passes validation (tested).
- Step 4: `examples/pizero-relays.yaml` and `.md`, the README "Supported boards" table, the daemon.md "Board notes" table, and CHANGELOG.
- Verified: 190 passed (Python 3.13). The board and GPIO manager tests also pass on Python 3.9. `ruff` is clean and the docs build passes.
- **Not ticked: Step 3 (bench test).** It needs a human with a Pi Zero W running Raspberry Pi OS Lite: outputs, inputs, and daemon CPU and memory over 24 h. Record the OS and the RPi.GPIO version here. "Done when" waits on this sign-off.
