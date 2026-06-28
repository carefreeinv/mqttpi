# Trailer — Door, Lights, Breakaway & Level

Minimal Pico W template for a camping trailer: entry door, breakaway switch, interior/porch/accent lights, propane and motion sensors, and MPU6050 leveling for campsite setup.

**Config file:** [`trailer.yaml`](trailer.yaml)

---

## Purpose

Provide essential trailer MQTT visibility—security (door, breakaway, motion), lighting control, propane alarm, and pitch/roll level—without tanks, TPMS, or slideouts.

---

## Quick Start

```bash
cd /home/pi/mqttpi
cp examples/sites/trailer.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Mount MPU6050 on trailer tongue box floor or rigid frame member.
2. Wire breakaway switch as NC chain to GP22.
3. Calibrate level when trailer is chocked and level.

```bash
mosquitto_pub -h 192.168.1.50 -t mobile/trailer/level/calibrate -m "1"
```

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Pico W** (`board: picow`) |
| Profile | `sensors` |
| Device ID | `trailer-main` |

**Why Pico W?** Small footprint, low standby power on battery, adequate GPIO + I2C for level sensor.

---

## Hardware List

| Item | Role |
|------|------|
| Pico W | Trailer MQTT node |
| MPU6050 (0x68) | Level (I2C GP0/GP1) |
| Door reed switch | Entry |
| Breakaway switch | Safety chain |
| PIR motion | Interior |
| Propane detector contact | GP6 |
| Relay or MOSFET | Lights (12 V) |

---

## Pin / Bus Map

### Buses

| Bus | Enabled |
|-----|---------|
| I2C | Yes — GP0 SDA, GP1 SCL |
| 1-Wire / SPI / I2S / PWM | Disabled |

### GPIO

| Pin | Alias | HA Name |
|-----|-------|---------|
| 7 | `entry_door` | Entry Door |
| 22 | `breakaway_active` | Breakaway Switch |
| 2 | `interior_light` | Interior Light |
| 3 | `porch_light` | Porch Light |
| 4 | `accent_strip` | Accent Strip |
| 6 | `propane_detector` | Propane Detector |
| 20 | `motion_interior` | Interior Motion |

---

## Sensors

### Level sensor (MPU6050)

| Reading | Notes |
|---------|-------|
| Pitch, Roll, Deviation | 3 s publish |
| Level OK | **2.0°** threshold (relaxed vs RV) |

Calibrate: `mobile/trailer/level/calibrate`

### TPMS / BMS / Victron / CAN / I2S

**Not used.**

---

## MQTT / Home Assistant Entities

**Base topic:** `mobile/trailer`  
**Client ID:** `mqttpi-trailer-main`

| Entity | Type |
|--------|------|
| Entry Door | binary_sensor (door) |
| Breakaway Switch | binary_sensor (safety) |
| Interior Motion | binary_sensor (motion) |
| Propane Detector | binary_sensor (gas) |
| Interior/Porch/Accent | switch |
| Level Pitch/Roll/Deviation | sensor |
| Level OK | binary_sensor |

---

## Design Decisions

1. **2.0° level threshold** — Small trailers tolerate more tilt for sleeping.
2. **Breakaway debounce 20 ms** — Fast safety signal to HA/tow vehicle alert path.
3. **No analog tanks** — Keeps ADC pins free; upgrade path is [`rv.yaml`](rv.yaml).
4. **PWM off** — Binary lighting only for wiring simplicity on entry-level builds.
5. **GP7 for door** — Leaves GP0/1 exclusively for I2C level.

---

## FAQ

**Q: Breakaway shows active while hitched.**  
A: Switch should open when chain pulls; verify NC wiring and `pull: up` configuration.

**Q: Level wrong on tongue jack extension?**  
A: Recalibrate after jack changes; mount IMU on trailer frame not movable jack plate.

**Q: Add TPMS later?**  
A: Copy `sensors.tpms` from [`rv.yaml`](rv.yaml); requires UART GP8/GP9.

**Q: Power from trailer 12 V?**  
A: Use buck converter 12 V→5 V with fuse; common ground with coach circuits.

**Q: Motion while camping bears?**  
A: HA arm/disarm when door closed and occupancy mode away.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`rv.yaml`](rv.yaml) | Full RV with tanks + TPMS |
| [`cargo-trailer.yaml`](cargo-trailer.yaml) | Cargo security focus |
| [`camper-top.yaml`](camper-top.yaml) | Truck camper + TPMS |
| [`../level-accelerometer.yaml`](../level-accelerometer.yaml) | Level tuning |

---

## Open Questions

- Bluetooth LE beacon on breakaway for phone alert out of MQTT range?
- Integrated weight-distribution hitch tension sensor on analog pin?
- Combine with tow vehicle TPMS in one HA dashboard?