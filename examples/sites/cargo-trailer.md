# Cargo Trailer — Ramp Door, Bay Lights & Security

Pico W template for an enclosed cargo trailer: ramp and side door contacts, interior/exterior lighting, motion security, tie-down zone sense, and trailer-to-tow connectivity detection.

**Config file:** [`cargo-trailer.yaml`](cargo-trailer.yaml)

---

## Purpose

Monitor cargo access points, provide work lighting control, detect motion in the bay, confirm trailer electrical connection to tow vehicle, and expose tie-down anchor status—optimized for **`maximum_gpio`** profile with buses disabled to free pins.

---

## Quick Start

```bash
cd /home/pi/mqttpi
cp examples/sites/cargo-trailer.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Wire ramp and side doors with NC reeds on pull-up inputs.
2. Use relay modules for high-current LED bay and exterior work lights.
3. `brake_connection` typically taps 12 V from tow vehicle charge circuit via optocoupler.

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Pico W** (`board: picow`) |
| Profile | `maximum_gpio` |
| Device ID | `cargo-trailer` |

**Why Pico W?** Maximum GPIO availability without consuming pins for I2C/SPI; ideal for door + light + security I/O only.

---

## Hardware List

| Item | Role |
|------|------|
| Pico W | Trailer MQTT node |
| Magnetic contacts ×2 | Ramp, side door |
| PIR motion | Cargo bay |
| Relay/MOSFET ×3 | Interior bay, exterior work, accent |
| Tie-down switch | Anchor armed sense |
| 7-pin brake/charge sense | Connectivity input |
| Optional temp switch | High-temp alert input (GP20) |

---

## Pin / Bus Map

### Buses

All buses **disabled** (I2C, SPI, I2S, 1-Wire) to maximize GPIO.

### GPIO

| Pin | Alias | HA Name |
|-----|-------|---------|
| 0 | `ramp_door` | Ramp Door |
| 1 | `side_door` | Side Door |
| 2 | `interior_bay` | Interior Bay Lights |
| 3 | `exterior_work` | Exterior Work Light |
| 4 | `accent_strip` | Accent Strip |
| 6 | `motion_cargo` | Cargo Bay Motion |
| 10 | `tie_down_zone` | Tie-Down Anchor Armed |
| 11 | `brake_connection` | Trailer Connected |
| 20 | `temp_probe_alert` | High Temp Alert |

### MQTT aliases

| Key | Maps to |
|-----|---------|
| `ramp_door_contact` | `ramp_door` |
| `side_door_contact` | `side_door` |

---

## Sensors

### Level / TPMS / BMS / Victron / CAN / I2S

**Not used.** For mobile shop with audio see [`cargo-trailer-workshop.yaml`](cargo-trailer-workshop.yaml). For leveling see [`trailer.yaml`](trailer.yaml).

---

## MQTT / Home Assistant Entities

**Base topic:** `mobile/cargo-trailer`  
**Client ID:** `mqttpi-cargo-trailer`

| Entity | device_class / icon |
|--------|---------------------|
| Ramp Door | garage_door |
| Side Door | door |
| Cargo Bay Motion | motion |
| Tie-Down Anchor Armed | safety |
| Trailer Connected | connectivity |
| High Temp Alert | heat |
| Interior/Exterior/Accent | switch |

---

## Design Decisions

1. **`maximum_gpio` profile** — No bus pin reservations; GP0/GP1 usable for doors.
2. **Security-first inputs** — Motion + doors + connectivity for theft alerts in HA.
3. **Tie-down zone** — Optional load secure interlock before departure automations.
4. **High temp on GPIO** — Placeholder for cheap bimetal or DS18B20 comparator; not full ADC monitoring.
5. **No level sensor** — Cargo haulers rarely need pitch; add I2C in fork if hauling sensitive equipment.

---

## FAQ

**Q: Lights drain trailer battery.**  
A: HA auto-off after N minutes; use low-quiescent buck supply for Pico.

**Q: Motion triggers when door opens.**  
A: Delay motion arm 30 s after door close; position PIR away from ramp airflow.

**Q: Trailer Connected always OFF.**  
A: Sense 12 V from pin on 7-way via divider/opto; adjust threshold.

**Q: Upgrade to workshop trailer?**  
A: Switch to Pi 4 [`cargo-trailer-workshop.yaml`](cargo-trailer-workshop.yaml) for machine circuits + I2S.

**Q: Add GPS tracking?**  
A: Separate LTE module; publish to same MQTT broker for HA map card.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`cargo-trailer-workshop.yaml`](cargo-trailer-workshop.yaml) | Pi 4 mobile shop |
| [`snowmobile-trailer.yaml`](snowmobile-trailer.yaml) | Enclosed hauler + heat |
| [`trailer.yaml`](trailer.yaml) | Camping trailer + level |
| [`../maximum-gpio.yaml`](../maximum-gpio.yaml) | GPIO-only profile |

---

## Open Questions

- Interior CO alert for gasoline equipment stored in bay?
- Load cell on tie-down zone for strap tension MQTT?
- Ramp open → auto exterior work light with timeout?
- Fleet ID in `base_topic` for multiple cargo units?