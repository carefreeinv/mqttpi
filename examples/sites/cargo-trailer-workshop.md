# Cargo Trailer Workshop — Mobile Shop with I2S Alerts

Raspberry Pi 4 template for a **converted cargo trailer mobile shop**: machine circuits (table saw, compressor, welder), dust collector, bay/side doors, shore power sense, HVAC, PWM overhead dimming, and eight numbered I2S WAV tracks for shift and hazard alerts.

**Config file:** [`cargo-trailer-workshop.yaml`](cargo-trailer-workshop.yaml)

---

## Purpose

Run a fully MQTT-integrated mobile workshop: interlocked tool power, lighting scenes, motion security, shore power awareness, and audible alerts (door open, E-stop, welding reminder, low shore power) through I2S—mirroring fixed [`workshop.yaml`](workshop.yaml) at Pi 4 capability.

---

## Quick Start

```bash
cd /home/pi/mqttpi
cp examples/sites/cargo-trailer-workshop.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Install WAV files in `/opt/mqttpi/sfx/workshop/` (tracks 01–08).
2. Size shore cord and panel for welder + table saw **never simultaneous** unless panel rated for it—use HA interlocks.
3. Wire I2S amp for shop-floor audible alerts above machine noise.

Door-open alert example (HA automation):

```yaml
# Publish "3" to mobile/cargo-workshop/sfx/play when bay_door opens
```

Stop playback: `mobile/cargo-workshop/sfx/stop`

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Raspberry Pi 4** (`board: pi4`) |
| Profile | `sensors` |
| Device ID | `cargo-workshop` |

**Why Pi 4?** I2S SFX with `state_topic`/`stop_topic`, multiple heavy relay logic, shore/HVAC, and headroom for future I2C power monitors.

---

## Hardware List

| Item | Role |
|------|------|
| Raspberry Pi 4 | Shop controller |
| I2S DAC/amp | Shift/hazard SFX |
| Contactor/relay panel | Dust, saw, compressor, welder |
| Shore power sense | GP17 |
| Bay + side door contacts | GP5, GP6 |
| PIR motion | GP16 |
| HVAC cool relay | GP26 |
| PWM dimmer | GP12 overhead |
| 1-Wire / I2C | Future env + current sensors |

---

## Pin / Bus Map

### Buses

| Bus | Enabled | Pins |
|-----|---------|------|
| 1-Wire | Yes | GPIO 4 |
| I2C | Yes | SDA 2, SCL 3 |
| I2S | Yes | BCLK 18, LRCK 19, DIN 20, DOUT 21 |
| PWM | Yes | GP12, GP13 |

### GPIO

| Pin | Alias | HA Name |
|-----|-------|---------|
| 5 | `bay_door` | Bay Ramp Door |
| 6 | `side_access` | Side Access Door |
| 16 | `motion_shop` | Shop Motion |
| 17 | `shore_connected` | Shore Power |
| 22 | `dust_collector` | Dust Collector |
| 23 | `table_saw` | Table Saw Circuit |
| 24 | `compressor` | Air Compressor |
| 25 | `welder_circuit` | Welder Outlet |
| 27 | `work_overhead` | Work Overhead Lights |
| 14 | `accent_bench` | Bench Accent |
| 26 | `hvac_cool` | Shop HVAC Cool |
| 12 | `overhead_dim` | Overhead Dimmer |

---

## Sensors

### Level / TPMS / BMS / Victron / CAN

**Not used.**

### I2S SFX

| # | Alias | File | Use |
|---|-------|------|-----|
| 1 | `shift_start` | `01-shift-start.wav` | Begin work |
| 2 | `shift_end` | `02-shift-end.wav` | End work |
| 3 | `door_alert` | `03-door-open.wav` | Bay open |
| 4 | `dust_collector_on` | `04-dust-on.wav` | Dust reminder |
| 5 | `hazard_stop` | `05-e-stop.wav` | E-stop |
| 6 | `welding_active` | `06-welding.wav` | Welding reminder |
| 7 | `break_chime` | `07-break.wav` | Break time |
| 8 | `low_power` | `08-low-power.wav` | Low shore |

- Directory: `/opt/mqttpi/sfx/workshop`
- Command: `mobile/cargo-workshop/sfx/play`
- State: `mobile/cargo-workshop/sfx/status`
- Stop: `mobile/cargo-workshop/sfx/stop`
- `play_by_number: true`

---

## MQTT / Home Assistant Entities

**Base topic:** `mobile/cargo-workshop`  
**Client ID:** `mqttpi-cargo-workshop`

| Group | Entities |
|-------|----------|
| Access | Bay Ramp Door, Side Access, Motion |
| Power | Shore Power |
| Machines | Dust, Table Saw, Compressor, Welder |
| Lighting | Overhead, Bench, Dimmer |
| HVAC | Shop HVAC Cool |
| SFX | 8 buttons + play/stop/status topics |

---

## Design Decisions

1. **Pi 4 in mobile shop** — Same I2S pattern as [`house.md`](house.md) and [`club.md`](club.md).
2. **Welder on dedicated circuit** — HA should interlock with compressor/saw for shore ampacity.
3. **SFX state + stop topics** — Allows HA to show “playing” and cancel alerts.
4. **Shore sense** — Drives `low_power` SFX when generator/shore insufficient.
5. **I2C reserved** — INA219 per circuit for overload MQTT without re-wiring GPIO map.

---

## FAQ

**Q: Run on generator instead of shore?**  
A: Reuse `shore_connected` input for gen sense or add second binary; tune `low_power` automation thresholds.

**Q: E-stop hardware vs SFX track 5?**  
A: SFX is notification only—install physical E-stop cutting contactor coil power.

**Q: Dust collector automation?**  
A: Turn on dust before saw; play track 4 if saw ON without dust.

**Q: Fixed workshop instead?**  
A: Use [`workshop.yaml`](workshop.yaml) on Pico W without I2S.

**Q: Trailer movement detection?**  
A: Add MPU6050 from [`trailer.yaml`](trailer.yaml) in merged config for “shop mode” only when parked.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`workshop.yaml`](workshop.yaml) | Fixed Pico shop |
| [`cargo-trailer.yaml`](cargo-trailer.yaml) | Cargo security only |
| [`house.yaml`](house.yaml) | Pi 4 I2S residential |
| [`club.yaml`](club.yaml) | Venue SFX patterns |

---

## Open Questions

- Per-circuit INA219 thresholds on I2C for MQTT overload cutoffs?
- NFC tap-in for shift_start SFX instead of HA button?
- Interlock welder when bay_door open (ventilation)?
- Cellular MQTT when trailer away from home broker?