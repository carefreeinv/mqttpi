# Store — Retail Background Music & Floor I/O

Pi 4 template for a retail shop or small chain location: **continuous streaming background music** over I2S, optional **70 V ceiling-speaker distribution**, door/motion monitoring, display lighting, and short announcement SFX that duck the music.

**Config file:** [`store.yaml`](store.yaml)

---

## Purpose

Run a **store audio node** on one MQTT device:

- **Background music (BGM)** — looped local playlist, HTTP/Icecast stream, or Snapcast feed from head office
- **I2S output** — PCM5102 DAC line-out to a **70 V commercial amp**, or a **class-D I2S amp module** for a single-zone boutique
- **SFX overlay** — door chime, “closing soon,” thank-you prompts; BGM ducks automatically
- **Floor GPIO** — front/stockroom doors, sales-floor motion, open sign, display accent + dimmer, amp power relay, HVAC fan

Typical use cases:

- Licensed BGM during business hours with HA schedule automations
- Corporate stream pushed to many stores via Icecast or Snapcast
- Amp power tied to “store open” scene (relay on `amp_power`)
- Motion-aware volume or lighting (HA automation on `motion_floor`)

---

## Quick Start

```bash
cp examples/sites/store.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit mqtt.host, stream URLs, device.id
```

1. Install BGM files under `/opt/mqttpi/bgm/` (MP3/FLAC/OGG).
2. Install SFX under `/opt/mqttpi/sfx/store/` (tracks 01–03).
3. Wire I2S DAC or amp module (see **Amplifier wiring** below).
4. Connect `amp_power` relay if the amplifier needs a hardware enable.
5. Start mqttpi; device **Store** appears in HA with a **Background Music** entity.

Control stream from MQTT:

```bash
# Play / pause
mosquitto_pub -h 192.168.1.50 -t site/store/audio/stream/set -m "ON"
mosquitto_pub -h 192.168.1.50 -t site/store/audio/volume/set -m "40"
mosquitto_pub -h 192.168.1.50 -t site/store/audio/source/set -m "icecast"

# Door chime (ducks BGM)
mosquitto_pub -h 192.168.1.50 -t site/store/sfx/play -m "1"
```

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Raspberry Pi 4** (`board: pi4`) |
| Profile | `sensors` |
| Device ID | `store-main` |

**Why Pi 4?** Continuous decode/playback (MP3/HTTP stream), filesystem playlists, Wi-Fi/Ethernet reliability, concurrent MQTT + GPIO. Pico W cannot run RTMP/heavy streaming to I2S — see [`speaker-zones-8.md`](../speaker-zones-8.md) for zone **enable** only on Pico.

---

## Amplifier Wiring

I2S on Pi 4 (BCM 18–21) outputs **digital PCM**. You need a DAC, AES transmitter, or I2S-integrated amp; **70 V is not available directly from I2S pins**.

For **70 V ceiling retail**, prefer one of two paths — both keep the **Pi-to-rack link simple** and leave balancing/70 V transformation to the commercial amp:

| Path | Chain | When to use |
|------|-------|-------------|
| **A — Unbalanced analog** (default) | I2S → DAC → **RCA / 3.5 mm** → 70 V amp **LINE IN** | Short rack run (&lt; ~6 m), amp has RCA/AUX/screw-terminal inputs |
| **B — AES digital** | I2S → **AES3 transmitter** → 70 V amp **AES/EBU IN** | Longer Pi-to-amp run, noisy electrical environment, amp has digital input |

**Avoid** converting to **balanced analog XLR** on the Pi side unless the amp has no RCA/AUX and no AES input — unbalanced line or AES digital is the intended mqttpi store layout.

### Option A — 70 V via unbalanced line (default)

```
Pi 4 I2S → PCM5102 DAC → unbalanced RCA (or 3.5 mm TRS) → 70 V amp LINE IN → 70 V ceiling speakers
```

| Stage | Part examples | Notes |
|-------|---------------|-------|
| DAC | PCM5102, HiFiBerry DAC+ | Consumer **unbalanced** line out (~2 Vrms) |
| Cable | Shielded RCA pair or short TRS→dual-RCA | Keep run short; single ground reference at amp |
| Distribution | Bogen, Atlas, Pyle 70 V amp | Use **LINE**, **AUX**, or screw-terminal **unbalanced** input |
| Speakers | 70 V ceiling taps (5/10/15 W) | Amp handles constant-voltage distribution |

Set `buses.i2s.amp.profile: line_out_70v_unbalanced` and `signal_path: unbalanced_analog`.

**Wiring tips:** Common ground Pi DAC ↔ amp chassis. Do not run unbalanced analog next to AC feeders for tens of metres — use Option B instead.

### Option B — 70 V via I2S → AES3 (digital to amp)

```
Pi 4 I2S → AES3 transmitter → AES/EBU (XLR digital) → 70 V amp AES IN → 70 V ceiling speakers
```

| Stage | Part examples | Notes |
|-------|---------------|-------|
| AES bridge | I2S→AES3 module, pro DSP with digital out, amp-integrated USB/AES option | **XLR carries digital AES3**, not analog balanced audio |
| Amp | 70 V amp with **AES/EBU or SPDIF** input | Atlas, Ashly, some Biamp/JBL commercial units |
| Benefit | One digital cable Pi-rack | DAC + level alignment happen **inside the 70 V amp** |

Set `buses.i2s.amp.profile: aes_to_70v` and `signal_path: aes3_digital` (see commented block in `store.yaml`).

**Note:** AES3 is **AES/EBU** professional digital audio (typically 44.1/48 kHz PCM embedded in the stream). This is distinct from **analog balanced XLR** mic/line inputs.

### Option C — Boutique / single zone (20–200 W)

```
Pi 4 I2S → class-D I2S amp module → 4–8 Ω speakers (pair or parallel)
```

| Module | Power | Fit |
|--------|-------|-----|
| MAX98357A | ~3 W | Counter / kiosk only |
| TPA3116 dual board | 2×50 W | Small shop, one room |
| TPA3255 / Sure amp boards | 100–200 W | Loud open-floor retail |

Set `buses.i2s.amp.profile: class_d_direct` and update `power_stage` in YAML.

**Power supply:** Class-D boards need a **separate DC supply** sized to wattage (e.g. 24 V 5 A for 100 W). Do not power high-watt amps from the Pi.

### Option D — Zoned ceilings (many rooms)

Use a **70 V amp with zone relays**, or add a Pico W [`speaker-zones-8`](../speaker-zones-8.md) node for zone triggers while this Pi feeds the amp line input.

---

## Hardware List

| Item | Role |
|------|------|
| Raspberry Pi 4 | Store controller + audio streamer |
| PCM5102 DAC or I2S→AES3 bridge | Unbalanced line or digital feed to amp rack |
| 70 V amp + ceiling speakers | Multi-tap retail PA (options A or B) |
| Relay module ×3 | Open sign, display accent, amp power |
| PWM LED driver | Window display dimmer (GP12) |
| Door contacts ×2 | Front, stockroom |
| PIR / microwave motion | Sales floor (GP16) |
| MQTT broker | Mosquitto (local or cloud) |

---

## Pin / Bus Map

### Buses

| Bus | Enabled | Pins |
|-----|---------|------|
| I2C | Yes | SDA 2, SCL 3 (future temp/CO₂) |
| I2S | Yes | BCLK 18, LRCK 19, DIN 20, DOUT 21 |
| PWM | Yes | GP12, GP13 |
| 1-Wire | No | — |

### GPIO

| Pin | Alias | Direction | HA Name |
|-----|-------|-----------|---------|
| 5 | `front_door` | Input | Front Door |
| 6 | `stockroom_door` | Input | Stockroom Door |
| 16 | `motion_floor` | Input | Sales Floor Motion |
| 17 | `open_sign` | Output | Open Sign |
| 22 | `display_accent` | Output | Window Display Accent |
| 23 | `amp_power` | Output | Amplifier Power |
| 24 | `hvac_fan` | Output | HVAC Fan |
| 12 | `display_dim` | PWM | Display Dimmer |

---

## Background Music (Stream)

| Setting | Value |
|---------|-------|
| Command | `site/store/audio/stream/set` (`ON` / `OFF`) |
| State | `site/store/audio/stream/state` |
| Volume | `site/store/audio/volume/set` (0–100) |
| Source | `site/store/audio/source/set` (`local_playlist`, `icecast`, `snapcast`) |
| Autoplay | `autoplay_on_boot: true` |
| Default source | `local_playlist` → `/opt/mqttpi/bgm/` |

### Sources

| Alias | Type | Use |
|-------|------|-----|
| `local_playlist` | Directory shuffle loop | USB/synced MP3s, offline-friendly |
| `icecast` | HTTP MP3 stream | Corporate retail radio URL |
| `snapcast` | Snapcast client | HQ pushes one mix to all stores |

HA discovers **Store Background Music** as a controllable media entity (contract; exact component class TBD in daemon).

---

## I2S SFX (ducks BGM)

| # | Alias | File | HA Name |
|---|-------|------|---------|
| 1 | `door_chime` | `01-door-chime.wav` | SFX Door Chime |
| 2 | `closing_soon` | `02-closing-soon.wav` | SFX Closing Soon |
| 3 | `thank_you` | `03-thank-you.wav` | SFX Thank You |

- Directory: `/opt/mqttpi/sfx/store`
- Command: `site/store/sfx/play`
- `duck_stream: true` — lowers BGM to 15% during SFX, restores after 8 s

---

## MQTT / Home Assistant Entities

**Base topic:** `site/store`  
**Client ID:** `mqttpi-store-main`

| Category | Entities |
|----------|----------|
| Audio | Background Music (stream), volume, source select |
| Doors | Front Door, Stockroom Door |
| Occupancy | Sales Floor Motion |
| Lighting | Open Sign, Display Accent, Display Dimmer |
| HVAC | HVAC Fan |
| Power | Amplifier Power |
| SFX | Three announcement buttons + `sfx/play` |

GPIO topics: `{base_topic}/gpio/{alias}/state` (+ `/set` for outputs).

---

## Design Decisions

1. **Streaming first** — `buses.i2s.stream` is the primary feature; SFX is secondary with ducking.
2. **Unbalanced or AES to 70 V** — Default `line_out_70v_unbalanced` (RCA/AUX); `aes_to_70v` when the amp has AES/EBU in. No balanced-analog XLR from the Pi unless unavoidable.
3. **`amp_power` relay** — Hard-mutes amp at close; avoids idle hiss and saves standby power.
4. **Local playlist fallback** — Store keeps playing if WAN drops (important for strip malls).
5. **Icecast + Snapcast** — Two common enterprise patterns without locking to one vendor.
6. **Pi 4 not Pico** — Decode + buffer + long playlists exceed Pico W RAM/CPU.

---

## FAQ

**Q: Can I use RTMP or Spotify directly?**  
A: Not on Pico W. On Pi 4, the planned daemon targets **HTTP MP3/Icecast, local files, and Snapcast**. Spotify/RTMP usually need `ffmpeg` or a separate streamer feeding line-in — integrate via HA or pipe into Snapcast.

**Q: 70 V vs 8 Ω?**  
A: **70 V** for many ceiling speakers and long cable runs (grocery, big-box). **8 Ω class-D** for one room or low speaker count. I2S always lands on a **DAC, AES transmitter, or class-D amp** first.

**Q: Unbalanced RCA vs balanced XLR vs AES?**  
A: **Prefer unbalanced RCA/line** into the 70 V amp’s AUX/LINE input for short rack wiring. **Prefer AES3** (digital on AES/EBU XLR) for a longer or noisier Pi-to-amp run — the amp’s internal DAC handles level and distribution. Skip **analog balanced XLR** from the Pi unless the amp lacks RCA and AES.

**Q: Is AES the same as balanced analog XLR?**  
A: No. **AES3** is a **digital** stream on an XLR connector. **Balanced analog XLR** is a different electrical format. This example’s `aes_to_70v` path is digital end-to-end to the amp’s AES input.

**Q: How loud is 200 W on 70 V?**  
A: Tap each ceiling speaker (e.g. 5 W × 20 speakers = 100 W program). Size the amp for headroom, not max wattage on every tap.

**Q: License compliance for BGM?**  
A: mqttpi does not track PRO licensing. Use a licensed service (Soundtrack Your Brand, Mood Media, etc.) or your own licensed files in `local_playlist`.

**Q: Door chime over music?**  
A: `duck_stream` lowers music during WAV playback. For a hard interrupt, add a mixer or separate paging input on the amp.

**Q: Multi-store rollout?**  
A: Point all stores’ `icecast` or `snapcast` sources at HQ; keep `device.id` unique per site (`store-main-001`, …).

**Q: Implementation status?**  
A: **Config contract** — stream/ducking runtime not merged yet; BMS bridge is separate today.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`club.yaml`](club.yaml) | Venue announcements + lighting (event vs retail BGM) |
| [`house.yaml`](house.yaml) | Residential I2S chimes |
| [`speaker-zones-8.yaml`](../speaker-zones-8.yaml) | Pico W zone enables for multi-zone 70 V |
| [`workshop.yaml`](workshop.yaml) | Pico GPIO-only site (no audio) |

---

## Open Questions

- Fade-in at open / fade-out at close (volume ramp in HA vs daemon)?
- Tie `motion_floor` to +3 dB daytime volume?
- UPS on Pi + amp for brief outage during closing announcements?
- Per-department Snapcast streams for mall kiosks vs one store mix?