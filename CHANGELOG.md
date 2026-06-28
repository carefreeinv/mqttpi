# Changelog

All notable changes to [mqttpi](https://github.com/carefreeinv/mqttpi) are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Planned

- PWM, CAN, I2C expanders, Victron in unified daemon
- Pico W firmware / MicroPython port
- MCP23017 expander driver

## [0.2.0] - 2026-06-28

### Added

- **Unified daemon** (`python3 -m mqttpi`) — one process for GPIO and optional BMS
- GPIO subsystem: `direction: output` (HA switch) and `direction: input` (HA binary_sensor) with MQTT command topics
- `mqttpi/gpio/` — RPi.GPIO backend, mock backend (`--mock-gpio`), HA discovery
- `mqttpi/mqtt/` — shared MQTT client for GPIO command handling
- `mqttpi/bms/subsystem.py` — BMS poll loop as a daemon subsystem
- `mqttpi.service` — systemd unit template for the unified daemon (manual install only)
- [daemon.md](daemon.md) — daemon quick start, supported examples, troubleshooting

### Changed

- Package version `0.1.0` → `0.2.0`
- **Supported runtime examples:** [`relay-bank-16`](examples/relay-bank-16.yaml) (16 relay outputs) and [`jbd-bms`](examples/jbd-bms.yaml) (BMS)
- `mqttpi.bms.bridge` retained for BMS-only / `--once` diagnostics
- `mqttpi-bms.service` — notes unified daemon alternative; manual install only
- README, example docs, and `config.example.md` updated for foreground daemon usage
- `scripts/stage_docs.py` — stages `daemon.md` into the docs site nav
- systemd units are templates only — nothing installed automatically

## [0.1.3] - 2026-06-28

### Changed

- Public release polish — removed internal dev notes (bms0 prototype, first-project / broker-deployment status)
- Site example docs and `mqttpi-bms.service` no longer hardcode `/home/pi/mqttpi`; systemd unit uses `%h/mqttpi` (edit if installed elsewhere)
- Cargo trailer deployment guide rewritten for public use

## [0.1.2] - 2026-06-28

### Added

- `speaker-zones-8` example — 8-zone speaker amp control on native Pico W GPIO (GP0–GP7), based on `relay-bank-16`
- `sites/store` example — retail Pi 4 template with I2S streaming BGM, 70 V / class-D amp profiles, and ducking SFX

### Changed

- `sites/store` — 70 V signal paths prefer **unbalanced analog (RCA)** or **I2S → AES3** to amp; avoid balanced analog XLR from Pi

## [0.1.1] - 2026-06-28

### Added

- `relay-bank-16` example — 16 relays on native Pico W GPIO (GP0–GP15), no expanders

### Changed

- `relay-bank-32` example — corrected to **2× MCP23017** (16 GPIO per chip @ `0x20`, `0x21`); was wrongly documented as 4× chips with 8 pins each

## [0.1.0] - 2026-06-28

### Added

- YAML configuration model with `config.yaml` + gitignored `secrets.yaml` merge
- Home Assistant MQTT discovery as default (`ON`/`OFF`, retained state)
- Board profiles: **Pico W** (default), Pi 4/5 secondary
- Optional peripheral toggles: 1-Wire, I2C, SPI, I2S, PWM (all off in `maximum_gpio` profile)
- Contiguous PWM bank on Pico W: GP8–GP15 (8 channels)
- **36+ example configs** with matching `.md` documentation
- **Site templates:** house, workshop, club, RV, motorhome, skoolie, trailers, semi, camper-top, cargo-trailer, etc.
- Protocol examples: JBD BMS, TPMS, level (MPU6050), CAN (OBD, RV-C, can2040), Victron VE.Direct / VE.Can
- **JBD BMS bridge** (`python3 -m mqttpi.bms.bridge`) — wired UART monitor with Home Assistant discovery
- **`relay-bank-32`** example — 32 relays via 4× MCP23017 on I2C (Pico W)
- **`robot`** example — differential drive rover template
- **Deployment guide:** `projects/cargo-trailer/`
- `examples/README.md` index; `config.example.md` starter doc
- systemd unit template: `mqttpi-bms.service`

### Notes

- Most subsystems are **configuration contracts**; only the BMS UART bridge is runnable in v0.1.0.

[Unreleased]: https://github.com/carefreeinv/mqttpi/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/carefreeinv/mqttpi/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/carefreeinv/mqttpi/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/carefreeinv/mqttpi/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/carefreeinv/mqttpi/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/carefreeinv/mqttpi/releases/tag/v0.1.0