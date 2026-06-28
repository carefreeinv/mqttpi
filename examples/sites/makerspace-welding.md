# Makerspace Welding — Fume Extraction & Welder Outlets

Pico W zone node for a welding / metal shop: shop door, motion, **PN532 RFID entry reader**, fume extractor and make-up air relays, two welder outlets, grinding area power, overhead lighting with PWM dimming, and shop temperature.

**Config file:** [`makerspace-welding.yaml`](makerspace-welding.yaml)

Part of the multi-node makerspace layout — see [`makerspace.md`](makerspace.md).

---

## Purpose

Monitor and control ventilation and machine power in a communal metal shop. Welder outlets are MQTT switches; HA automations require fume extraction before energizing welders and can enforce fire-safety lockouts after hours.

---

## Quick Start

```bash
cp examples/sites/makerspace-welding.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Mount Pico W in a NEMA enclosure away from weld spatter and strong EM fields.
2. Wire fume extractor and make-up air contactors per local code.
3. Use properly rated contactors for welder circuits — GPIO drives **coils only**.
4. Deploy mqttpi; device **Makerspace Welding** appears in HA.

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Pico W** (`board: picow`) |
| Profile | `sensors` |
| Device ID | `makerspace-welding` |

**Why Pico W?** Dedicated low-cost node for a high-noise RF environment; isolate welding shop I/O from other zones.

---

## Hardware List

| Item | Role |
|------|------|
| Raspberry Pi Pico W | Welding shop MQTT node |
| Relay module ×6+ | Fume extractor, make-up air, welders, grinding, lights |
| Magnetic door contact | Shop entry |
| PIR or microwave occupancy | Shop motion (GP20) |
| Fume extractor contactor | GP21 coil driver |
| Make-up air fan contactor | GP22 |
| NTC thermistor or analog temp transmitter | GP26 |
| PN532 RFID module (I2C) | Member card reader at welding shop entry |
| I2C sensor (future) | CO monitor, differential pressure |

---

## Pin / Bus Map

### Buses

| Bus | Enabled | Pins |
|-----|---------|------|
| 1-Wire | No | Pin 7 (reserved) |
| I2C | Yes | SDA 0, SCL 1 — PN532 @ 0x24 |
| RFID IRQ | GP7 | PN532 interrupt (optional) |
| SPI | No | — |
| I2S | No | — |
| PWM | Yes | GP8–15 |

### GPIO

| Pin | Alias | Direction | HA Name |
|-----|-------|-----------|---------|
| 6 | `shop_door` | Input (inverted) | Welding Shop Door |
| 20 | `motion_shop` | Input | Welding Shop Motion |
| 21 | `fume_extractor` | Output | Fume Extractor |
| 22 | `make_up_air` | Output | Make-Up Air Fan |
| 2 | `welder_outlet_1` | Output | Welder Outlet 1 |
| 3 | `welder_outlet_2` | Output | Welder Outlet 2 |
| 4 | `grinding_power` | Output | Grinding Area Outlet |
| 5 | `shop_overhead` | Output | Overhead Lights |
| 8 | `overhead_dim` | PWM | Overhead Dimmer |
| 26 | `shop_temp` | Analog input | Welding Shop Temperature |

---

## RFID (member tracking)

PN532 on I2C at the welding shop entry. Certify members for hot-work access in HA before enabling welder outlets.

| Setting | Value |
|---------|-------|
| Reader | `pn532_i2c` @ **0x24** |
| Zone tag | `welding` |
| Scan topic | `site/makerspace/welding/rfid/scan` |
| Access mode | `track` |

See [`../rfid.md`](../rfid.md).

---

## MQTT / Home Assistant Entities

**Base topic:** `site/makerspace/welding`  
**Client ID:** `mqttpi-makerspace-welding`

| Entity | Alias | Type |
|--------|-------|------|
| Welding Shop Door | `shop_door` | binary_sensor (door) |
| Welding Shop Motion | `motion_shop` | binary_sensor (motion) |
| Fume Extractor | `fume_extractor` | switch |
| Make-Up Air Fan | `make_up_air` | switch |
| Welder Outlet 1 | `welder_outlet_1` | switch |
| Welder Outlet 2 | `welder_outlet_2` | switch |
| Grinding Area Outlet | `grinding_power` | switch |
| Overhead Lights | `shop_overhead` | switch |
| Overhead Dimmer | `overhead_dim` | number (0–100%) |
| Welding Shop Temperature | `shop_temp` | sensor (°C, 60 s) |
| Last Card UID | `rfid_last_uid` | sensor (text) |
| RFID Scan Count | `rfid_scan_count` | sensor (total_increasing) |
| RFID Access Granted | `rfid_access_granted` | binary_sensor (lock) |

Topic pattern: `{base_topic}/gpio/{alias}/state` (+ `/set` for outputs and dimmer). RFID: `{base_topic}/rfid/*`.

---

## Design Decisions

1. **Separate fume extractor and make-up air** — Balanced ventilation for enclosed metal shops; HA can run both together.
2. **Two welder outlets** — Typical for communal TIG/MIG stations; expand with another node if needed.
3. **Grinding outlet separate from welders** — Different duty cycle and scheduling; still requires ventilation in HA.
4. **Ventilation as switch, not hardware interlock** — mqttpi publishes state; HA enforces rules. Add hardware E-stop for code compliance.
5. **PN532 entry RFID** — Log who entered the welding shop; HA can require hot-work certification UID before `welder_outlet_*` ON.
6. **I2C reserved** — Future CO or pressure differential sensors for failed-exhaust alerts.

---

## FAQ

**Q: How do I block welders when ventilation is off?**  
A: HA automation: `welder_outlet_1` and `welder_outlet_2` may turn ON only when `fume_extractor` is ON. Optionally require `make_up_air` as well.

**Q: Will weld EMI affect the Pico W?**  
A: Keep the board in a metal enclosure, use optocoupler relay modules, and separate signal wiring from welder leads.

**Q: Can I interlock gas solenoids?**  
A: Add relay outputs on GP9–15 (PWM bank free) or a second zone node; wire solenoid coil through the same HA ventilation gate.

**Q: Fire code requires constant exhaust — can HA turn it off?**  
A: Use hardware hold circuits for life-safety exhaust. mqttpi switches are for **supplemental** shop ventilation, not fire-rated smoke evacuation unless engineered accordingly.

**Q: Can only certified welders energize outlets?**  
A: HA automation: on `rfid/scan`, if UID is in `input_text.welding_certified` → allow welder switches; else deny and notify staff.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`makerspace.md`](makerspace.md) | Multi-zone architecture overview |
| [`makerspace-woodshop.yaml`](makerspace-woodshop.yaml) | Sibling woodshop zone |
| [`makerspace-digifab.yaml`](makerspace-digifab.yaml) | Sibling digifab zone |
| [`../rfid.md`](../rfid.md) | RFID reader reference |
| [`workshop.yaml`](workshop.yaml) | Dust-collection patterns for wood side |