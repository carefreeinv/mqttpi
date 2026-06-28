# Skoolie BMS — JBD House Pack + Level + Coach GPIO

Raspberry Pi 4 template for a solar skoolie **power stack**: JBD BMS on USB-TTL, MPU6050 leveling, and minimal GPIO for solar enable, galley lights, diesel heat, and entry door—intended as a companion or upgrade to [`skoolie.yaml`](skoolie.yaml).

**Config file:** [`skoolie-bms.yaml`](skoolie-bms.yaml)

---

## Purpose

Expose JBD lithium house battery telemetry (voltage, current, SOC, cell data per BMS protocol) to MQTT/Home Assistant while retaining coach leveling and essential relay outputs on the same Pi 4 node.

---

## Quick Start

```bash
cp examples/sites/skoolie-bms.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Connect JBD BMS TTL to USB adapter → `/dev/ttyUSB0` (9600 baud).
2. Enable I2C in `raspi-config`; wire MPU6050 on SDA 2 / SCL 3.
3. Install systemd unit if using `mqttpi-bms.service` pattern.
4. Verify BMS entities under HA device **Skoolie Power**.

```bash
# Optional: udev rule for stable USB path
ls -l /dev/ttyUSB0
```

Pair with Victron: copy `ve_direct` sections from [`rv-victron.yaml`](rv-victron.yaml).

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Raspberry Pi 4** (`board: pi4`) |
| Device ID | `skoolie-bms` |
| HA device name | Skoolie Power |

**Why Pi 4?** USB serial for JBD, reliable polling interval (30 s), Linux udev for `/dev/ttyUSB0`, and I2C level on controller 1 pins.

---

## Hardware List

| Item | Role |
|------|------|
| Raspberry Pi 4 | BMS + GPIO host |
| JBD BMS (UART) | House lithium pack |
| USB-TTL adapter | `/dev/ttyUSB0`, 9600 8N1 |
| MPU6050 @ 0x68 | Level sensor (I2C) |
| Relay outputs ×3 | Solar, galley, diesel heat |
| Door contact | Entry (GP27) |
| 1-Wire (optional) | GP4 for cell/bay temps |

---

## Pin / Bus Map

### Buses

| Bus | Enabled | Notes |
|-----|---------|-------|
| 1-Wire | Yes | GPIO 4 |
| I2C | Yes | Controller 1, SDA 2, SCL 3 |
| SPI / I2S | Disabled | — |

### GPIO

| Pin | Alias | HA Name |
|-----|-------|---------|
| 17 | `solar_enable` | Solar Charge Enable |
| 22 | `galley_lights` | Galley Lights |
| 23 | `diesel_heat` | Diesel Furnace |
| 27 | `entry_door` | Entry Door |

---

## Sensors

### Level sensor (MPU6050)

| Reading | Alias |
|---------|-------|
| Pitch | `level_pitch` |
| Roll | `level_roll` |
| Level OK | `is_level` (1.5°) |

Calibrate: `mobile/skoolie-bms/level/calibrate`

### BMS (JBD)

| Setting | Value |
|---------|-------|
| Protocol | `jbd` |
| Port | `/dev/ttyUSB0` |
| Baud | 9600 |
| Poll interval | 30 s |
| Response timeout | 2 s |
| HA device | Skoolie House Pack (`device_id: jbd_skoolie_house`) |

Typical published fields (per JBD protocol): pack voltage, current, SOC, cell voltages, temperatures, alarms.

### TPMS / Victron / CAN / I2S

**Not used** in this file. Add Victron VE.Direct blocks from [`rv-victron.md`](rv-victron.md) if MPPT/shunt share the Pi.

---

## MQTT / Home Assistant Entities

**Base topic:** `mobile/skoolie-bms`  
**Client ID:** `mqttpi-skoolie-bms`

| Group | Source |
|-------|--------|
| BMS sensors | JBD poll → HA battery entities |
| Level | Pitch, Roll, Level OK |
| GPIO | Solar, Galley, Diesel, Entry Door |

BMS topics typically under `{base_topic}/bms/...` (see [`../jbd-bms.yaml`](../jbd-bms.yaml)).

---

## Design Decisions

1. **Pi 4 required for BMS** — Pico W lacks USB host for TTL adapter at scale.
2. **30 s poll interval** — Balances BMS UART traffic vs fresh SOC for dashboards.
3. **Reduced GPIO set** — Full coach I/O remains on [`skoolie.yaml`](skoolie.yaml) Pico if split architecture.
4. **Same level chip as coach configs** — Familiar calibrate topic for HA automations.
5. **`retry_delay: 10`** — Recovers from transient USB disconnect without hammering port.

---

## FAQ

**Q: `/dev/ttyUSB0` changes after reboot.**  
A: Add udev rule matching USB serial adapter VID/PID → symlink `/dev/jbd-bms`.

**Q: BMS reads zero or timeout.**  
A: Confirm 9600 baud, TX/RX crossover, and that JBD Bluetooth is not exclusively locking UART.

**Q: Can one Pi run skoolie.yaml + skoolie-bms.yaml merged?**  
A: Yes on Pi 4—merge `bms`, `sensors`, and `pins` sections; resolve pin conflicts.

**Q: Victron Cerbo already publishes SOC—duplicate?**  
A: Disable one source in HA or use Cerbo for solar and mqttpi for JBD-only pack.

**Q: Is diesel heat safe on same Pi as BMS?**  
A: Relay control is fine; use galvanic isolation on door/engine signals near high current paths.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`skoolie.yaml`](skoolie.yaml) | Full coach GPIO on Pico |
| [`rv-victron.yaml`](rv-victron.yaml) | VE.Direct + RV-C |
| [`../jbd-bms.yaml`](../jbd-bms.yaml) | JBD protocol reference |

---

## Open Questions

- Publish BMS cell imbalance alerts to dedicated MQTT topic for push notifications?
- Automatic solar disable on `entry_door` open (theft mode)?
- Second USB port for Victron MPPT VE.Direct without UART contention?
- Historical SOC logging interval vs BMS wear?