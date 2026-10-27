# Plan: 1-Wire and I2C sensor drivers, plus config schema for an I2C ADC and a current/voltage monitor

- **Value:** medium
- **Priority:** P3
- **Slug:** onewire-i2c-sensor-drivers
- **Preferred models:** mid, coding-agent
- **Assignee:** ai
- **Depends on:** ha-numeric-sensor-entities

## Progress
- [x] Step 1: DS18B20 1-Wire driver
- [x] Step 2: I2C climate sensor drivers (BME280, SHT3x/SHT4x)
- [x] Step 3: Config schema for an I2C ADC (ADS1115-class) under `analog_input`
- [x] Step 4: Config schema for a current/voltage monitor (INA219/INA226-class)
- [ ] Step 5: Optional implementations of the two new schemas
- [ ] Step 6: Docs and bench test
- [ ] Done when holds

## Goal
The documented 1-Wire and I2C sensor config contracts work on Linux boards, and the config contract gains two missing device types: an I2C ADC so boards without an ADC can use `analog_input`, and a current/voltage/power monitor. Readings publish through the shared numeric sensor entities.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `examples/sensors-i2c-onewire.yaml`, `examples/analog-inputs.yaml` (Pico W ADC pins only), `config.example.yaml` (`buses.onewire`, `buses.i2c`), `mqttpi/sensors/` (from `ha-numeric-sensor-entities`).

## Depends on (detail)
- `ha-numeric-sensor-entities` — drivers implement its `SensorDriver` Protocol and publish through it.

## Constraints
- Keep the existing documented keys; new device types follow the same style (`type`, `address`, `bus`, `alias`, `unit`, scaling).
- Linux 1-Wire via the kernel `w1` sysfs interface (no extra dependency); I2C via `smbus2` declared as an optional extra.
- Bus errors time out and mark the entity unavailable; never hang the scheduler.
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python per `.anchor/conventions.md`: small composable classes, Protocols or narrow ABCs, dependency injection over globals; pytest for tests; user-facing changes documented in `README.md`/`daemon.md`/`config.example.md` and `CHANGELOG.md` `[Unreleased]` when they ship.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | DS18B20 driver reading `/sys/bus/w1/devices/*/w1_slave` (or `temperature`), with fake sysfs in tests | `mqttpi/sensors/onewire.py`, tests | Unit tests with fixture files | small |
| 2 | BME280 and SHT3x/SHT4x drivers over `smbus2` with fake bus in tests | `mqttpi/sensors/i2c_climate.py`, tests | Unit tests | mid |
| 3 | Specify `analog_input` with `source: ads1115` (address, channel, gain, scaling) and document it | `config.example.md`, `examples/analog-inputs.yaml`, `examples/analog-inputs.md` | Docs build passes; example loads in tests | small |
| 4 | Specify a `power_monitor` sensor type (INA219/INA226-class: address, shunt ohms, max current; entities voltage, current, power) | `config.example.md`, new example yaml/md | Docs build passes; example loads in tests | small |
| 5 | If the owner approves, implement drivers for both new schemas | `mqttpi/sensors/ads1115.py`, `mqttpi/sensors/ina2xx.py`, tests | Unit tests | mid |
| 6 | Changelog and bench test on real sensors | `CHANGELOG.md` | Bench result recorded | human |

## Risks
- Driver count grows. Mitigation: each driver small, behind one Protocol, with a fake.
- I2C bus lockups. Mitigation: timeouts, bus recovery note in docs.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes for all drivers
- `examples/sensors-i2c-onewire.yaml` runs with fakes
- New schemas documented with examples; bench results recorded

## Handoff

- Implemented on branch `feature/onewire-i2c-sensor-drivers`, stacked on `feature/pwm-output-driver`.
- **Steps 1–4 are done**, with unit tests that use a fake w1 sysfs and fake I2C register maps:
  - The BME280 compensation is checked against the datasheet worked example.
  - The Sensirion CRC is checked against its reference value.
- **Step 5 is not started.** The plan says "if the owner approves". The ADS1115 and INA219/INA226 schemas are documented, and those entries are skipped with a warning.
- **Step 6 (bench) is open:**
  - DS18B20 on `dtoverlay=w1-gpio`;
  - BME280 at 0x76;
  - SHT31 and SHT41 at 0x44;
  - unplug a sensor during a run and confirm only that entity goes offline.
