# Skoolie — Emergency Exits, Solar, Climate & Level

Pico W template for a converted school bus: emergency exit and roof hatch monitoring, solar charge enable, galley/lounge/bunk lighting with PWM, dual mini-split HVAC, diesel furnace, engine sense, and MPU6050 leveling.

**Config file:** [`skoolie.yaml`](skoolie.yaml)

---

## Purpose

Monitor safety openings on a skoolie build, control lighting and climate relays, enable solar charging, and provide pitch/roll feedback for leveling on uneven boondocking sites—all via MQTT/Home Assistant.

---

## Quick Start

```bash
cp examples/sites/skoolie.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Mount MPU6050 under chassis floor or rear axle area (rigid mount).
2. Wire NC exit contacts; test that open door triggers within 30 ms debounce on rear/side exits.
3. Solar enable relay typically controls charge controller remote terminal.
4. Calibrate level on a known-flat pad after install.

```bash
mosquitto_pub -h 192.168.1.50 -t mobile/skoolie/level/calibrate -m "1"
```

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Pico W** (`board: picow`) |
| Profile | `sensors` |
| Device ID | `skoolie-main` |

**Why Pico W?** Balances GPIO count, Wi-Fi, I2C level, and 1-Wire expansion for a mobile bus without needing Pi-class USB/BMS on the same node.

---

## Hardware List

| Item | Role |
|------|------|
| Pico W | Coach MQTT node |
| MPU6050 (0x68) | Level on I2C |
| 1-Wire (GP7) | Optional interior/fridge temps |
| Emergency exit contacts ×2 | Rear and side |
| Roof hatch contact | GP6 |
| Entry door contact | GP2 |
| Relay module | Solar, lights, HVAC, diesel heat |
| Engine run sense | GP20 |

---

## Pin / Bus Map

### Buses

| Bus | Enabled | Pins |
|-----|---------|------|
| 1-Wire | Yes | GP7 |
| I2C | Yes | GP0 SDA, GP1 SCL |
| PWM | Yes | GP8–15 (`lounge_dim` on GP8) |

### GPIO

| Pin | Alias | HA Name |
|-----|-------|---------|
| 2 | `entry_door` | Entry Door |
| 3 | `rear_exit` | Rear Emergency Exit |
| 4 | `side_exit` | Side Emergency Exit |
| 6 | `roof_hatch` | Roof Hatch |
| 20 | `engine_running` | Engine Running |
| 21 | `solar_enable` | Solar Charge Enable |
| 22, 16, 17 | lights | Galley, lounge, bunk |
| 18, 19 | HVAC | Front/rear mini-splits |
| 26 | `diesel_heat` | Diesel Furnace |
| 8 | `lounge_dim` | Lounge Dimmer |

---

## Sensors

### Level sensor (MPU6050)

| Reading | Notes |
|---------|-------|
| Pitch, Roll, Deviation | 2 s retained publish |
| Level OK | 1.5° threshold |

Calibrate topic: `mobile/skoolie/level/calibrate`

### TPMS / BMS / Victron / CAN / I2S

**Not in this config.** For JBD house pack monitoring use [`skoolie-bms.yaml`](skoolie-bms.yaml). For Victron solar/shunt use [`rv-victron.yaml`](rv-victron.yaml) pattern.

---

## MQTT / Home Assistant Entities

**Base topic:** `mobile/skoolie`  
**Client ID:** `mqttpi-skoolie-main`

| Group | Entities |
|-------|----------|
| Safety openings | Entry, Rear/Side Exit, Roof Hatch |
| Power | Engine Running, Solar Enable |
| Comfort | Galley/Lounge/Bunk lights, Lounge Dimmer |
| HVAC | Front/Rear Mini-Split, Diesel Furnace |
| Level | Pitch, Roll, Deviation, Level OK |

---

## Design Decisions

1. **Fast debounce on exits (30 ms)** — Rapid alarm path for egress monitoring.
2. **Solar enable default ON (`initial: true`)** — Matches typical “allow charging” default; disable in HA when storing bus.
3. **Dual mini-split outputs** — One relay per head unit; HA handles heat/cool mode logic.
4. **1-Wire on GP7** — Does not conflict with I2C level on GP0/1.
5. **Separate from skoolie-bms** — GPIO coach node can run on Pico while BMS runs on Pi 4 with USB-TTL.

---

## FAQ

**Q: Should I combine this with skoolie-bms?**  
A: Run two configs on two boards, or merge YAML carefully—BMS requires Pi 4 + `/dev/ttyUSB0`.

**Q: Exit alarm while driving with hatch vent open?**  
A: HA automation: only arm exit alerts when `engine_running` is OFF and speed (from GPS) is zero.

**Q: Level sensor on flexible floor?**  
A: Mount to steel chassis member; foam subfloor flex causes false pitch.

**Q: Diesel heat interlock?**  
A: Require `engine_running` OFF and propane/CO clear before enabling `diesel_heat` in HA.

**Q: How is this different from RV?**  
A: Skoolie emphasizes **emergency exits**, dual mini-splits, solar enable, diesel heat—not slideouts/awning/tanks.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`skoolie-bms.yaml`](skoolie-bms.yaml) | JBD house battery on Pi 4 |
| [`rv.yaml`](rv.yaml) | Travel trailer tanks + TPMS |
| [`motorhome.yaml`](motorhome.yaml) | Larger coach TPMS layout |
| [`../level-accelerometer.yaml`](../level-accelerometer.yaml) | MPU6050 details |

---

## Open Questions

- Tie rear exit to exterior siren + MQTT when any exit opens while armed?
- Add TPMS for bus dual rear wheels?
- Integrate WVO/tank heat zones on 1-Wire?
- Roof hatch rain sensor GPIO when hatch open?