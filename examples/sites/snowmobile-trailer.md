# Snowmobile Trailer — Sled Security, Ramp Heat & Lights

Pico W template for an enclosed snowmobile hauler: ramp door, front/rear sled tie-down confirmation, interior/exterior lighting, ramp heat mat, cabin heat fan, motion, freeze alert, and trailer connectivity.

**Config file:** [`snowmobile-trailer.yaml`](snowmobile-trailer.yaml)

---

## Purpose

Help owners verify sleds are secured before transit, control heat and lights for cold-weather loading, monitor interior motion, and detect loss of tow connection or freezing conditions inside the enclosed trailer.

---

## Quick Start

```bash
cp examples/sites/snowmobile-trailer.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Wire tie-down switches to detect strap tension or pin engagement.
2. Ramp heat mat and heat fan via relays sized for 12 V DC loads.
3. Enable 1-Wire on GP7 if adding DS18B20 freeze sensing later (GPIO alert on GP20 is placeholder).

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Pico W** (`board: picow`) |
| Profile | `sensors` |
| Device ID | `sled-trailer` |

**Why Pico W?** Cold-weather enclosed trailer needs simple GPIO + optional 1-Wire temps without Pi overhead.

---

## Hardware List

| Item | Role |
|------|------|
| Pico W | Trailer controller |
| Ramp door contact | GP0 |
| Sled tie-down switches ×2 | GP1, GP2 |
| Relay outputs | Lights, ramp heat, heat fan, accent |
| PIR motion | GP14 |
| Tow connectivity sense | GP15 |
| Freeze/bimetal switch | GP20 |
| 1-Wire bus (optional) | GP7 for DS18B20 |

---

## Pin / Bus Map

### Buses

| Bus | Enabled |
|-----|---------|
| 1-Wire | Yes — GP7 |
| I2C / SPI / I2S | No |

### GPIO

| Pin | Alias | HA Name |
|-----|-------|---------|
| 0 | `ramp_door` | Ramp Door |
| 1 | `sled_front_tied` | Front Sled Secured |
| 2 | `sled_rear_tied` | Rear Sled Secured |
| 3 | `interior_light` | Interior Light |
| 4 | `exterior_flood` | Exterior Flood |
| 6 | `accent_blue` | Accent Lights |
| 10 | `ramp_heat` | Ramp Heat Mat |
| 11 | `cabin_heat_fan` | Enclosed Heat Fan |
| 14 | `motion_interior` | Interior Motion |
| 15 | `brake_connection` | Trailer Connected |
| 20 | `low_temp_alert` | Freeze Alert Input |

### MQTT aliases

| Key | Maps to |
|-----|---------|
| `sled_1_secure` | `sled_front_tied` |
| `sled_2_secure` | `sled_rear_tied` |

---

## Sensors

### Level / TPMS / BMS / Victron / CAN / I2S

**Not used.**

### 1-Wire (optional expansion)

Bus enabled on GP7 for future temperature strings along trailer length.

---

## MQTT / Home Assistant Entities

**Base topic:** `mobile/snowmobile-trailer`  
**Client ID:** `mqttpi-sled-trailer`

| Entity | Notes |
|--------|-------|
| Ramp Door | garage_door |
| Front/Rear Sled Secured | lock |
| Interior Motion | motion |
| Trailer Connected | connectivity |
| Freeze Alert Input | cold |
| Ramp Heat Mat / Heat Fan | switch — pre-trip warmup |
| Lights | interior, flood, accent |

---

## Design Decisions

1. **Sled secure interlocks** — HA can block “departure” scene unless both tie-downs ON.
2. **Ramp heat separate from cabin fan** — Mat warms ramp surface; fan circulates air to prevent condensation.
3. **1-Wire enabled** — Natural fit for multi-point freeze monitoring in long enclosed trailers.
4. **Accent blue** — Common aesthetic for sled decks; cosmetic relay on GP6.
5. **No I2C** — Frees pins; cargo variant [`cargo-trailer.yaml`](cargo-trailer.yaml) also avoids I2C.

---

## FAQ

**Q: Preheat automation before ride day?**  
A: HA schedule: if outside temp < X, enable `ramp_heat` and `cabin_heat_fan` for 30 min.

**Q: Tie-down switches false positive.**  
A: Use strain or pin switches that only close under proper tension; debounce 100 ms.

**Q: Freeze alert without 1-Wire?**  
A: GP20 accepts bimetal thermostat closing at 32 °F; or migrate to DS18B20 on 1-Wire.

**Q: Power budget on battery?**  
A: Ramp mats draw high current—monitor battery voltage; auto-off via HA.

**Q: Difference from cargo-trailer?**  
A: Snowmobile variant adds **sled tie-downs**, **heat**, and **freeze** inputs.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`cargo-trailer.yaml`](cargo-trailer.yaml) | General enclosed cargo |
| [`trailer.yaml`](trailer.yaml) | Camping trailer |
| [`../sensors-i2c-onewire.yaml`](../sensors-i2c-onewire.yaml) | 1-Wire temp add-on |

---

## Open Questions

- CO monitor for running sleds during load (dangerous—prefer procedural lockout)?
- GPS geofence “left storage yard” → require tie-downs ON notification?
- Bluetooth temp beacons in trailer vs 1-Wire wired?
- Solar trickle on trailer battery for long-term heat standby?