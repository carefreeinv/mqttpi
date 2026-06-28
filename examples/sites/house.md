# House — Residential Monitoring & Control

Example site config for a fixed residential installation: door contacts, HVAC relay calls, accent lighting, water leak detection, and I2S sound effects for door chimes and alerts.

**Config file:** [`house.yaml`](house.yaml)

---

## Purpose

Monitor entry points (front, back, garage), drive porch and living-room accent lighting (including PWM dimming), call HVAC heat/cool/fan relays, detect water leaks, and play numbered WAV alerts through an I2S DAC/amp. All entities publish to MQTT with Home Assistant discovery enabled.

Typical use cases:

- Door-open notifications with chime SFX
- Garage door state in HA dashboards
- Accent light scenes and entry dimmer control
- HVAC interlock or zone control via relay outputs
- Leak sensor integration for automations

---

## Quick Start

```bash
cp examples/sites/house.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit mqtt.host, device.id, and secrets.yaml credentials
```

1. Install WAV files under `/opt/mqttpi/sfx/` (see I2S SFX section).
2. Wire GPIO through 3.3 V–safe interfaces (relay modules, opto-isolated inputs).
3. Enable I2C and 1-Wire in `raspi-config` if using those buses later.
4. Start mqttpi; entities appear in HA under device **House**.

Test SFX from HA or MQTT:

```bash
mosquitto_pub -h 192.168.1.50 -t home/house/sfx/play -m "1"
```

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Raspberry Pi 4** (`board: pi4`) |
| Profile | `sensors` |
| Device ID | `house-main` |

**Why Pi 4?** I2S audio output needs stable Linux audio stack, filesystem access for WAV libraries, and enough CPU for concurrent MQTT + SFX playback. Residential installs usually have mains power and space for a full Pi.

---

## Hardware List

| Item | Role |
|------|------|
| Raspberry Pi 4 | Main controller |
| I2S DAC/amp (e.g. PCM5102, MAX98357A) | Door chimes and alert SFX |
| Reed/magnetic door contacts ×3 | Front, back, garage |
| Relay module ×5 | Accent lights, HVAC heat/cool/fan |
| PWM-capable LED driver | Entry dimmer (GP12) |
| Water leak sensor (dry contact) | GP27 |
| 1-Wire bus (optional future) | Temperature sensors on pin 4 |
| I2C bus | Future environmental sensors (SDA 2, SCL 3) |
| MQTT broker | e.g. Mosquitto on `192.168.1.50` |

---

## Pin / Bus Map

### Buses

| Bus | Enabled | Pins / Notes |
|-----|---------|--------------|
| 1-Wire | Yes | GPIO 4 |
| I2C | Yes | Controller 1, SDA 2, SCL 3 |
| SPI | No | — |
| I2S | Yes | BCLK 18, LRCK 19, DIN 20, DOUT 21 |
| PWM | Yes | GP12, GP13 |

### GPIO

| Pin | Alias | Direction | HA Name |
|-----|-------|-----------|---------|
| 5 | `front_door` | Input (pull-up, inverted) | Front Door |
| 6 | `back_door` | Input | Back Door |
| 16 | `garage_door` | Input | Garage Door |
| 17 | `porch_accent` | Output | Porch Accent Lights |
| 22 | `living_accent` | Output | Living Room Accent |
| 23 | `hvac_heat` | Output | HVAC Heat Call |
| 24 | `hvac_cool` | Output | HVAC Cool Call |
| 25 | `hvac_fan` | Output | HVAC Fan |
| 27 | `water_leak` | Input | Water Leak |
| 12 | `dim_entry` | PWM output | Entry Dimmer (0–100%) |

### MQTT aliases

| Alias key | Maps to |
|-----------|---------|
| `front_door_contact` | `front_door` |
| `back_door_contact` | `back_door` |
| `garage_door_contact` | `garage_door` |

---

## Sensors

### Level sensor

**Not used** in this config.

### TPMS

**Not used.**

### BMS

**Not used.**

### Victron

**Not used.**

### CAN

**Not used.**

### I2S SFX

| # | Alias | File | HA Button |
|---|-------|------|-----------|
| 1 | `door_chime` | `01-door-chime.wav` | SFX Door Chime |
| 2 | `doorbell` | `02-doorbell.wav` | SFX Doorbell |
| 3 | `alarm_beep` | `03-alarm.wav` | SFX Alarm |
| 4 | `garage_notify` | `04-garage.wav` | SFX Garage Alert |

- Directory: `/opt/mqttpi/sfx`
- Command topic: `home/house/sfx/play` (publish track number or alias)
- HA discovers one button entity per track

---

## MQTT / Home Assistant Entities

**Base topic:** `home/house`  
**Client ID:** `mqttpi-house-main`  
**Discovery prefix:** `homeassistant`

| Entity type | Topic pattern | Examples |
|-------------|---------------|----------|
| Binary sensor | `{base_topic}/gpio/{alias}/state` | Front Door, Water Leak |
| Switch | `{base_topic}/gpio/{alias}/state` + `/set` | Porch Accent, HVAC Fan |
| Number (dimmer) | `{base_topic}/gpio/dim_entry/state` + `/set` | Entry Dimmer |
| SFX button | Discovery per track | SFX Door Chime |
| SFX command | `home/house/sfx/play` | Publish `1`–`4` |

All GPIO states use retain + QoS 1. Payloads: `ON` / `OFF`.

---

## Design Decisions

1. **Pi 4 over Pico W** — I2S SFX and expandable storage for a large WAV library; house has continuous power.
2. **Inverted door inputs with pull-up** — Matches normally-closed magnetic reed wiring (open = LOW).
3. **Separate HVAC heat/cool/fan outputs** — Works with standard 24 V relay panels without a single “mode” wire.
4. **PWM on GP12** — Hardware PWM pin on Pi 4 for flicker-free entry dimming.
5. **1-Wire + I2C enabled but lightly used** — Room for DS18B20 room temps or I2C motion/CO sensors without pin conflicts.
6. **Numbered SFX tracks** — HA automations can call `home/house/sfx/play` with a number; aliases allow human-readable MQTT too.

---

## FAQ

**Q: Door shows “open” when closed.**  
A: Toggle `invert: true` on the pin or swap NO/NC on the reed switch. Confirm pull resistor matches wiring (`pull: up` expects switch to ground when active).

**Q: No sound from I2S amp.**  
A: Verify WAV format (16-bit PCM, common sample rates), DAC wiring on BCLK/LRCK/DOUT, and that files exist under `/opt/mqttpi/sfx/`. Test with `mosquitto_pub` to `home/house/sfx/play`.

**Q: HVAC relays chatter.**  
A: Use interlocking in HA so heat and cool are never ON together; add minimum run times in automations.

**Q: Can I add a garage door opener?**  
A: Yes—add a momentary output pin and a `button` or `switch` with pulse automation in HA. Keep existing `garage_door` contact for state feedback.

**Q: Should I enable MQTT TLS?**  
A: For LAN-only brokers, `tls: false` is typical. Enable TLS and credentials in `secrets.yaml` if the broker is exposed beyond the home network.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`club.yaml`](club.yaml) / [`club.md`](club.md) | Another Pi 4 + I2S venue template |
| [`workshop.yaml`](workshop.yaml) / [`workshop.md`](workshop.md) | Tool/relay layout without audio |
| [`cargo-trailer-workshop.yaml`](cargo-trailer-workshop.yaml) | Mobile shop with I2S shift alerts |
| [`../home-assistant.yaml`](../home-assistant.yaml) | HA entity reference |
| [`../pi4-pwm-relay.yaml`](../pi4-pwm-relay.yaml) | Pi 4 PWM + relay patterns |

---

## Open Questions

- Should porch/living accent share a single PWM zone or stay binary relays?
- Integrate 1-Wire room temperatures into HVAC automations?
- Add camera/doorbell MQTT triggers instead of GPIO for front door?
- Night-mode volume scaling for I2S SFX?
- Backup power (UPS) signaling on a dedicated GPIO?