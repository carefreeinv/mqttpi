# Changelog

All notable changes to [mqttpi](https://github.com/carefreeinv/mqttpi) are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **MQTT Last Will** — `MqttConnection` registers a retained `offline` will on `{base_topic}/status` before connecting, so a crashed or disconnected node is marked offline by the broker; `online` is re-published after every successful (re)connect ([daemon.md](daemon.md#availability-and-last-will))
- `mqtt.keepalive` config key (default `60`, unchanged)
- **Resilient MQTT connect** — the daemon and `MqttConnection` start when the broker is unreachable, keep GPIO/BMS work running, and connect in the background with backoff (`mqtt.reconnect_min_s` / `mqtt.reconnect_max_s`, defaults 1 / 60 s); subscriptions, availability, HA discovery, and pin states are re-published after every reconnect; offline queue bounded by `mqtt.max_queued_messages` (default 1000) ([daemon.md](daemon.md#startup-and-reconnect))
- `MqttConnection.wait_connected(timeout)`
- `gpio.backend` config key (`rpi` default, `mock`), `GpioBackendUnavailable` error, `create_backend(strict=True)`, and `GpioManager.backend_name`; startup log names the active GPIO backend and board ([daemon.md](daemon.md#gpio-backend))
- **Packaging** — `pyproject.toml` (setuptools): `pip install "mqttpi @ git+https://github.com/carefreeinv/mqttpi"` provides the `mqttpi` and `mqttpi-bms` console scripts; `requires-python >= 3.9`; version single-sourced from `mqttpi/__init__.py`; `dev` / `docs` extras; pytest config moved from `pytest.ini` into `pyproject.toml`; release checklist in README
- **MQTT TLS** — `mqtt.tls` is now honored (it was documented but ignored): `true` for system CAs, or a mapping with `ca_certs`, `certfile`, `keyfile`, `insecure`; port defaults to 8883 when TLS is on and `mqtt.port` is unset; applies to the daemon and the standalone BMS bridge; TLS handshake failures are logged with a hint ([daemon.md](daemon.md#tls))
- **BMS shares the daemon's MQTT connection** — with GPIO and BMS in one daemon there is now one MQTT client (one client id, one Last Will) instead of two; BMS link health is published on `{base_topic}/bms/status` and BMS discovery uses `availability` [node status, BMS status] with `availability_mode: all`. Fixes a failing BMS poll marking the whole node (including GPIO entities) offline. Standalone `mqttpi-bms` gains Last Will + background reconnect; its client id is `bms.client_id` or `{mqtt.client_id}-bms` (**changed**: was `mqtt.client_id`) ([daemon.md](daemon.md#bms-and-the-mqtt-connection))
- `mqttpi.mqtt.factory` (`build_mqtt`, `base_topic_from`, `default_client_id`; still importable from `mqttpi.daemon`); `MqttConnection.base_topic`; `MqttConnection.disconnect()` now flushes queued messages before closing
- **Opt-in node-id discovery layout** — `mqtt.homeassistant.discovery_node_id: true` (or an explicit id) publishes discovery on `homeassistant/<component>/<node_id>/<object_id>/config` so broker ACLs can restrict each node to `homeassistant/+/<node_id>/#`; default layout unchanged; `unique_id`s unchanged; old flat-layout configs are cleared first (`discovery_clear_legacy`, default `true`); Mosquitto ACL example ([daemon.md](daemon.md#discovery-topics-and-per-node-acls)). `MqttConnection.publish(..., retain=)` override
- **Test suite and CI** — hardware-free unit tests for config loading, pin parsing, the GPIO manager (mock backend), HA discovery payload snapshots (`tests/snapshots/`), the JBD protocol (frames from the public protocol document) and UART client (fake serial port), the BMS bridge/subsystem, and a daemon smoke run; `.github/workflows/tests.yml` runs `ruff` and the unit suite on Python 3.9 / 3.11 / 3.13 for every push and pull request, plus an optional mosquitto integration job; minimal `ruff` config and `pytest-cov` in the dev extras
- **Command filter hook** — `mqttpi.gpio.commands` (`CommandRequest`, `CommandDecision`, `mutually_exclusive`, `block_while`); `GpioManager.add_command_filter` / `request_output`; `Daemon(command_filters=[...])` and `Daemon.gpio` / `Daemon.stop()` for embedding ([daemon.md](daemon.md#command-filters))
- **MCP23017 I2C GPIO expanders.** `expander: {chip, pin}` pins work as native outputs and inputs, with the same HA entities, topics and command filters. `ExpanderBackend` routes to the chips. Registers are re-applied after I2C errors or a chip reset (periodic check), polled inputs use one read per chip, and pins are released to inputs on shutdown. `--mock-gpio` uses in-memory chips. `examples/relay-bank-32.yaml` now runs. `default:`, `homeassistant:` and `bcm:` are accepted as aliases of `initial:`, `ha:` and `pin:` ([daemon.md](daemon.md#i2c-gpio-expanders-mcp23017))
- **Sensor drivers.** Added `ds18b20` (1-Wire through the kernel w1 sysfs; no new dependency), `bme280`/`bmp280`, `sht3x` and `sht4x` (I2C through `smbus2`, the optional extra `mqttpi[i2c]`). I2C buses open lazily and are shared, and a bus error marks only that sensor unavailable. `examples/sensors-i2c-onewire.yaml` now publishes these sensors. Two config schemas are documented ahead of their drivers: `analog_input` with `source: ads1115`, and the `ina219`/`ina226` power monitors (`examples/power-monitor.yaml`) ([daemon.md](daemon.md#sensor-drivers))
- **PWM outputs** — `direction: pwm_output` pins now run, where before they were skipped. They are Home Assistant `number` entities (0–100 %) with numeric `/set` (plus `ON`/`OFF`), clamping to `ha.min`/`ha.max`, `invert`, a safe `initial_duty`, and 0 % on shutdown. Software PWM is the default (`RPi.GPIO.PWM`); hardware PWM through the kernel sysfs is opt-in with `pwm_mode: hardware` (`pwm_chip`, `pwm_channel`). PWM commands pass through the command filters (`clamp_duty` filter added; `GpioManager.request_duty`). `GpioBackend.open_pwm`. Example `examples/linear-actuator-pwm.yaml` (dual-PWM H-bridge). **Note:** configs that already listed `pwm_output` pins now drive those pins ([daemon.md](daemon.md#pwm-outputs))
- **Numeric sensor entities** — `mqttpi.sensors`: `Reading` (values + timestamp + quality), `SensorDriver` Protocol, driver registry (`register_driver`), one polling scheduler thread with per-sensor interval, timeout, and staleness, and `NumericSensorPublisher` (HA `sensor` discovery with unit, device_class, state_class, per-entity availability). The daemon starts the sensor subsystem when `sensors` lists a type with a driver; types without a driver are skipped with a warning (existing example configs unchanged). Topics `{base_topic}/sensors/<alias>/state|attributes|availability`. Built-in `cpu_temperature` driver ([daemon.md](daemon.md#sensors-numeric-readings))
- **Board profiles** — `mqttpi.boards` with GPIO, hardware-PWM, and ADC metadata for `pi3`, `pi4`, `pi5`, `pizero` (Pi Zero W / Zero 2 W), and `picow`; the GPIO manager validates `pins[]` against `device.board` at startup (non-existent pin, duplicate pin, or pin claimed by an enabled bus → clear error; reserved/ADC/PWM mismatches → warning; unknown or missing board → not validated). Example `examples/pizero-relays.yaml` ([daemon.md](daemon.md#board-notes))
- Example `examples/linear-actuator.yaml` + `linear_actuator_interlock.py`: reversible actuator with a software interlock
- `RPi.GPIO` declared in `requirements.txt` for ARM Linux only (environment marker; x86 installs unchanged)
- `MqttConnection` options `base_topic`, `availability_topic`, `will`, `payload_available`, `payload_not_available`, `keepalive`, plus `add_connect_callback()` and `is_connected`
- GPIO switch / binary_sensor discovery payloads include `availability_topic`
- Test harness: `requirements-dev.txt`, `pytest.ini`, fake paho client (`tests/`), broker integration tests (`tests/integration/`, use `mosquitto` or `amqtt`, skipped if neither is installed)

- **Mermaid diagrams** — flow and wiring docs converted from ASCII; MkDocs loads Mermaid 11 via `extra_javascript` + `site_assets/mermaid-init.js` (theme-aware render on instant navigation)
- **Deployment guides** for [`house`](deployments/house.md), [`store`](deployments/store.md), and [`makerspace`](deployments/makerspace.md) site templates
- **Makerspace site templates** (one Pico W per shop zone):
  - [`makerspace-woodshop`](examples/sites/makerspace-woodshop.yaml) — dust collection, saw outlets, lighting
  - [`makerspace-welding`](examples/sites/makerspace-welding.yaml) — fume extraction, welder outlets, grinding area
  - [`makerspace-digifab`](examples/sites/makerspace-digifab.yaml) — laser exhaust, printer bench, electronics lighting
  - [`makerspace.md`](examples/sites/makerspace.md) — multi-node architecture overview
- **`rfid` example** — PN532 I2C member-card reader config contract (scan events, last UID, access hooks)
- PN532 RFID blocks on all three makerspace zone configs (`sensors.rfid`, `access.mode: track`)
- MkDocs **copyright footer** — `© Copyright Carefree Investments {year}` linking to [carefreeinv.com](https://carefreeinv.com) via `hooks/copyright.py`
- MkDocs **site logo** — custom `site_assets/logo.svg` (π mark with MQTT signal arcs and GPIO pin pads)

### Changed

- **Breaking (intentional):** a missing or broken GPIO library is now a startup error (exit 1) instead of a silent fallback to the mock backend. Use `--mock-gpio` or `gpio: {backend: mock}` to run without hardware; library users can pass `create_backend(strict=False)` for the old behavior
- `invert: true` on an **output** pin now makes it active-low (logical ON drives the pin LOW), as the example docs already described; previously `invert` was ignored for outputs. Configs that set `invert` on outputs will see the opposite pin level
- Mock GPIO inputs idle at the level of their pull resistor (`pull: up` reads high), like an unconnected real pin
- `MqttConnection.connect()` no longer raises when the broker is unreachable (uses paho `connect_async`); configuration errors raise `ValueError` from the constructor
- `BmsMqttPublisher.connect()` is non-blocking by default (`blocking=True` for one-shot use; `mqttpi.bms.bridge --once` keeps failing fast)
- HA discovery for GPIO is now published when `mqtt.homeassistant` is omitted entirely (discovery is documented as on by default)
- Availability messages on `{base_topic}/status` are always retained (previously followed `mqtt.retain`)
- Daemon availability topic now defaults to `mqttpi/{device.id}/status` when `mqtt.base_topic` is unset, matching the documented topic root and the GPIO topics (previously `mqttpi/status`)

- [`mkdocs.yml`](mkdocs.yml) — `pymdownx.superfences` custom `mermaid` fence; Mermaid.js CDN + init script
- [`scripts/stage_docs.py`](scripts/stage_docs.py) — stage `mermaid-init.js` into docs site
- Flow/wiring diagrams in [`README.md`](README.md), [`daemon.md`](daemon.md), site examples ([`store`](examples/sites/store.md), [`makerspace`](examples/sites/makerspace.md)), and protocol docs ([`rfid`](examples/rfid.md), [`jbd-bms`](examples/jbd-bms.md), CAN/Victron/TPMS, …) — ASCII → Mermaid
- [`examples/README.md`](examples/README.md) — makerspace zone index and `rfid` protocol entry
- [`README.md`](README.md), [`config.example.yaml`](config.example.yaml) — mention makerspace zone templates
- [`scripts/stage_docs.py`](scripts/stage_docs.py) — stage `rfid.md` into docs nav; copy `logo.svg` into `docs/assets/`
- [`mkdocs.yml`](mkdocs.yml) — use custom logo instead of Material `chip` icon
- [`workshop.md`](examples/sites/workshop.md) — cross-link to makerspace woodshop variant

### Fixed

- **GPIO input debounce** — an input change that settled inside the debounce window (a press or bounce shorter than `debounce_ms` ending in the other state) was never published, leaving the reported state stuck. Inputs now publish a value once it has been stable for `debounce_ms` (default 50 ms); bounces restart the timer. Note: state changes are now reported after `debounce_ms` rather than on the first edge ([daemon.md](daemon.md#gpio-inputs-and-debounce))
- **JBD read requests** — the request checksum wrongly included the `0xA5` read byte (`DD A5 03 00 FF 58 77`); requests now match the protocol (`DD A5 03 00 FF FD 77`). BMS firmware that validates request checksums did not answer before
- **JBD balancing cells** — balance bits were decoded in reverse order; bit n of the low balance word is now cell n+1 and the high word covers cells 17–32 (`balancing_cells` sensor)

### Planned

- PWM, CAN, I2C expanders, Victron, **RFID reader driver** in unified daemon
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