# TPMS — tire pressure and temperature

## Purpose

Integrate **433 MHz tire-pressure monitoring sensors** into Home Assistant via MQTT. Each wheel gets pressure and temperature sensors plus a **low-pressure binary alert**. Supports a UART decoder module or an I2C aggregation bridge talking to the RF front-end.

Reference layout for motorhomes, trailers, skoolies, and tow vehicles.

## Quick start

```bash
cp examples/tpms.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit mqtt.host, wheel sensor_id hex values
# Wire UART receiver to GP8/GP9 (or switch receiver.type to i2c)
```

**Pair a new sensor** (publish hex ID from receiver logs or label):

```bash
mosquitto_pub -h 192.168.1.50 -t mobile/tpms-node-01/tpms/pair -m "A1B2C3D4"
```

Replace `REPLACE_FL` … `REPLACE_RR` in config with your four sensor IDs, then deploy firmware when the TPMS runtime is available.

## Hardware

| Item | Spec |
|------|------|
| **Board** | Raspberry Pi Pico W (`profile: sensors`) |
| **RF path** | 433 MHz TPMS receiver (UART module default in YAML) |
| **UART receiver** | UART1 — TX **GP8**, RX **GP9**, **115200** baud |
| **I2C bridge (alt.)** | I2C0 — SDA **GP0**, SCL **GP1** — set `receiver.type: i2c` |
| **Sensors** | Common 433 MHz TPMS valves (protocol `tpms433`) |

### UART vs I2C bridge

| Mode | When to use |
|------|-------------|
| **UART** (`receiver.type: uart`) | Off-the-shelf USB/UART TPMS decoder boards that spit JSON or hex lines |
| **I2C** (`receiver.type: i2c`) | Custom aggregator MCU that decodes RF and exposes readings on I2C |

This example enables **I2C** in `buses` (for optional bridge) while the **receiver** block defaults to **UART** — pick one path in firmware; disable the unused bus if pin budget matters.

## Bus wiring

### UART receiver (default in config)

```
Pico W          TPMS UART decoder
──────          ─────────────────
GP8 (TX)  ───── RX   (often unused on listen-only decoders)
GP9 (RX)  ◄──── TX   (decoder output → Pico RX)
GND       ───── GND
3V3/5V    ───── VCC  (follow decoder spec — level-shift if 5 V)
```

### I2C bridge (alternative)

```
Pico W          I2C aggregator
──────          ───────────────
GP0 (SDA) ───── SDA
GP1 (SCL) ───── SCL
GND       ───── GND
```

Antenna placement: keep RF receiver away from Wi-Fi antenna and switching regulators; external 433 MHz antenna improves range on long rigs.

## MQTT / Home Assistant topics

Default `base_topic`: `mobile/tpms-node-01`

### Pairing

| Topic | Payload | Notes |
|-------|---------|-------|
| `{base_topic}/tpms/pair` | Hex `sensor_id` | Binds unknown ID to next free wheel slot (runtime-defined) |

### Per-wheel readings (retained)

For each wheel alias (`tpms_fl`, `tpms_fr`, `tpms_rl`, `tpms_rr`):

| Reading | Topic pattern | HA type | Units (config) |
|---------|---------------|---------|----------------|
| Pressure | `{base_topic}/sensors/{alias}_pressure/state` | sensor | **psi** |
| Temperature | `{base_topic}/sensors/{alias}_temperature/state` | sensor | **°F** |
| Low pressure | `{base_topic}/sensors/{alias}_low_pressure/state` | binary_sensor | ON = below `low_psi` |

### Thresholds (per wheel in YAML)

| Wheel | `low_psi` | `high_psi` |
|-------|-----------|------------|
| FL / FR / RL / RR | 32 | 80 |

Adjust for your tire placard — tow vehicles often need higher `low_psi` than trailer tires.

### Home Assistant discovery

Entities inherit `device_class` from config (`pressure`, `temperature`, `problem` for low pressure). Device name: **TPMS Node** with per-wheel `ha.name` (e.g. **Tire FL**).

## Design decisions

1. **433 MHz TPMS protocol** — Chosen for aftermarket valve-cap sensors common on RV/trailer upgrades (not factory BLE TPMS).
2. **UART default, I2C optional** — UART modules are quickest to prototype; I2C suits a custom RF MCU co-processor.
3. **Explicit `sensor_id` per wheel** — Avoids auto-mapping surprises when rotating tires; pair topic helps initial capture.
4. **psi / °F defaults** — US RV convention; override `sensors.tpms.units` for bar/°C.
5. **Retained publishes** — HA shows last known pressure after node reboot (stale data risk — add automations for offline nodes).
6. **Four-wheel template** — Extend `wheels:` list for dually or spare; each entry is independent.

## FAQ

**Q: How do I find my sensor hex ID?**  
A: Put the receiver in learn mode (runtime/firmware), inflate or trigger the sensor, and read the ID from serial logs — then publish it to the pair topic or paste into YAML.

**Q: UART or I2C — which should I build?**  
A: If you bought a finished 433 MHz UART decoder, use UART. If you are designing a Pico + SI4432/SX1278 front-end with a second MCU, I2C aggregation keeps RF code off the Wi-Fi core.

**Q: Will factory truck TPMS work?**  
A: Often **no** — OEM systems may use different frequencies, encryption, or BLE. This config targets generic **433 MHz `tpms433`** aftermarket caps.

**Q: What triggers the low-pressure binary sensor?**  
A: Pressure below `thresholds.low_psi` for that wheel (32 psi in the example). `high_psi` is available for over-pressure alerts in future runtime.

**Q: Can I monitor only the trailer axles?**  
A: Yes — delete unneeded `wheels` entries or run a second node with its own `base_topic` on the trailer Pico.

## Related examples

| Example | Relationship |
|---------|--------------|
| [`sites/trailer.yaml`](sites/trailer.yaml) | Trailer site layout |
| [`sites/motorhome.yaml`](sites/motorhome.yaml) | Motorhome template |
| [`sites/semi.yaml`](sites/semi.yaml) | Heavy tow / dually contexts |
| [`can-vehicle.yaml`](can-vehicle.yaml) | OBD speed/RPM (complements TPMS) |
| [`level-accelerometer.yaml`](level-accelerometer.yaml) | Coach level sensing |

## Implementation status

| Component | Status |
|-----------|--------|
| `examples/tpms.yaml` | **Config contract** |
| UART `tpms433` decoder | **Not implemented** |
| I2C bridge path | **Not implemented** |
| Pair topic handler | **Not implemented** |

**Config contract only** — no shipped firmware or Python bridge. See [`jbd-bms.md`](jbd-bms.md) for a working protocol reference in this repo.