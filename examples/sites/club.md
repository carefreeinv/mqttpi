# Club — Venue Lighting, Entry & I2S Announcements

Pi 4 template for a nightclub or event venue: zone lighting, entry mag-lock, HVAC, occupancy/fire-exit monitoring, and numbered I2S announcement tracks (last call, closing, VIP, emergency).

**Config file:** [`club.yaml`](club.yaml)

---

## Purpose

Centralize venue I/O on one MQTT node: stage/bar/dance accent relays, entry door and mag-lock, hall occupancy and fire exit status, HVAC supply/cool, stage PWM dimming, and staff-triggered announcement SFX through an I2S amplifier.

---

## Quick Start

```bash
cp examples/sites/club.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Place WAV files in `/opt/mqttpi/sfx/club/` (tracks 01–05).
2. Wire mag-lock relay (fail-secure vs fail-safe per local code).
3. Connect I2S amp to house PA or zone speakers.
4. Set `mqtt.host` and start mqttpi; device **Club Venue** appears in HA.

Play last call:

```bash
mosquitto_pub -h 192.168.1.50 -t site/club/sfx/play -m "1"
```

`play_by_number: true` accepts numeric payloads on the command topic.

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Raspberry Pi 4** (`board: pi4`) |
| Profile | `full_peripherals` |
| Device ID | `club-venue` |

**Why Pi 4?** I2S announcement audio, multiple lighting zones, 1-Wire/I2C expansion, and reliable Wi-Fi/Ethernet for a commercial venue back office.

---

## Hardware List

| Item | Role |
|------|------|
| Raspberry Pi 4 | Venue controller |
| I2S DAC/amp | Announcement playback |
| Relay modules ×6+ | Stage, bar, dance, mag-lock, HVAC |
| PWM dimmer driver | Stage dimmer (GP12) |
| Door contact + mag-lock | Entry (GP5 input, GP24 lock) |
| Occupancy sensor | Hall (GP6) |
| Fire exit contact | GP16 |
| 1-Wire / I2C (optional) | Crowd temp, CO2, beer-line monitoring |

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

| Pin | Alias | Direction | HA Name |
|-----|-------|-----------|---------|
| 5 | `entry_door` | Input | Entry Door |
| 6 | `occupancy_hall` | Input | Hall Occupancy |
| 16 | `fire_exit` | Input | Fire Exit |
| 17 | `stage_accent` | Output | Stage Accent |
| 22 | `bar_accent` | Output | Bar Accent |
| 23 | `dance_accent` | Output | Dance Floor Accent |
| 24 | `entry_lock` | Output (initial ON) | Entry Mag Lock |
| 25 | `hvac_supply` | Output | HVAC Supply Fan |
| 27 | `hvac_cool` | Output | HVAC Cooling |
| 12 | `stage_dim` | PWM | Stage Dimmer |

---

## Sensors

### Level sensor

**Not used.**

### TPMS

**Not used.**

### BMS

**Not used.**

### Victron

**Not used.**

### CAN

**Not used.**

### I2S SFX

| # | Alias | File | HA Name |
|---|-------|------|---------|
| 1 | `last_call` | `01-last-call.wav` | SFX Last Call |
| 2 | `closing_time` | `02-closing.wav` | SFX Closing |
| 3 | `vip_alert` | `03-vip.wav` | SFX VIP Alert |
| 4 | `emergency_tone` | `04-emergency.wav` | SFX Emergency Tone |
| 5 | `welcome` | `05-welcome.wav` | SFX Welcome |

- Directory: `/opt/mqttpi/sfx/club`
- Command: `site/club/sfx/play`

---

## MQTT / Home Assistant Entities

**Base topic:** `site/club`  
**Client ID:** `mqttpi-club-venue`

| Category | Entities |
|----------|----------|
| Doors / safety | Entry Door, Fire Exit |
| Occupancy | Hall Occupancy |
| Lighting | Stage/Bar/Dance Accent, Stage Dimmer |
| Access | Entry Mag Lock |
| HVAC | Supply Fan, Cooling |
| SFX | Five HA button entities + `site/club/sfx/play` |

GPIO topics: `{base_topic}/gpio/{alias}/state` (+ `/set` for outputs).

---

## Design Decisions

1. **`full_peripherals` profile** — All buses enabled for future sensors without config churn.
2. **Mag-lock `initial: true`** — Assumes fail-secure lock energized when Pi boots; adjust for your hardware.
3. **Separate accent zones** — Bar/dance/stage scenes independent in HA.
4. **`play_by_number: true`** — Staff tablets can fire announcements with a single digit.
5. **Fire exit as `opening` device class** — Distinct from main entry in dashboards and alerts.

---

## FAQ

**Q: Can emergency tone override music?**  
A: Route I2S to a mixer input that ducks main PA, or use a dedicated alert channel. mqttpi only plays the WAV; mixing is hardware/HA.

**Q: Mag-lock drops on Pi reboot.**  
A: Use a lock power supply with battery backup; consider a hardware hold relay. Set `initial` to match your lock polarity.

**Q: How to schedule last call nightly?**  
A: HA time automation → `site/club/sfx/play` payload `1`.

**Q: Occupancy stuck ON?**  
A: Increase `debounce_ms` (300 ms) or use microwave occupancy instead of PIR in a hallway.

**Q: Why Pi 4 instead of a sound card PC?**  
A: Integrates lighting/HVAC/doors on the same MQTT device as announcements—one discovery device in HA.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`house.yaml`](house.yaml) | Residential Pi 4 + I2S chimes |
| [`cargo-trailer-workshop.yaml`](cargo-trailer-workshop.yaml) | I2S shift/hazard alerts |
| [`semi.yaml`](semi.yaml) | Fleet-scale alerts + TPMS |
| [`../full-peripherals.yaml`](../full-peripherals.yaml) | Bus enablement reference |

---

## Open Questions

- Tie fire exit alarm to mandatory `emergency_tone` SFX and strobe relay?
- DMX/Art-Net integration for moving heads vs GPIO accents only?
- Separate MQTT base topic per room for multi-room venues?
- License/ASCAP logging for played announcement tracks?