# Changelog

All notable changes to [mqttpi](https://github.com/carefreeinv/mqttpi) are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `speaker-zones-8` example — 8-zone speaker amp control on native Pico W GPIO (GP0–GP7), based on `relay-bank-16`
- `sites/store` example — retail Pi 4 template with I2S streaming BGM, 70 V / class-D amp profiles, and ducking SFX

### Planned

- Unified mqttpi daemon (GPIO + BMS + CAN + expanders)
- Pico W firmware / MicroPython port
- MCP23017 expander driver
- Cargo trailer field deployment on dedicated Pico W

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
- **JBD BMS bridge** (`python3 -m mqttpi.bms.bridge`) — migrated from [bms0](https://github.com/carefreeinv/mqttpi) / local `~/bms0` project
- **`relay-bank-32`** example — 32 relays via 4× MCP23017 on I2C (Pico W)
- **`robot`** example — differential drive rover template
- **First project guide:** `projects/cargo-trailer/` (not deployed on shared GPIO-busy Pi)
- `examples/README.md` index; `config.example.md` starter doc
- systemd unit template: `mqttpi-bms.service`

### Notes

- Most subsystems are **configuration contracts**; only the BMS UART bridge is runnable in v0.1.0.
- Cargo trailer first deployment is documented but **not registered** with the central broker yet.

[Unreleased]: https://github.com/carefreeinv/mqttpi/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/carefreeinv/mqttpi/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/carefreeinv/mqttpi/releases/tag/v0.1.0