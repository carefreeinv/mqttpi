# Store deployment

This guide walks through deploying the store site template on a dedicated **Raspberry Pi 4** node.

**Config:** [`examples/sites/store.yaml`](../examples/sites/store.yaml)

**Documentation:** [`examples/sites/store.md`](../examples/sites/store.md)

## Hardware

| Item | Notes |
|------|-------|
| Board | **Raspberry Pi 4** (dedicated node) |
| Config template | `examples/sites/store.yaml` |
| I2S output | PCM5102 DAC → unbalanced RCA → 70 V amp LINE IN (default), or I2S→AES3 for digital amp input |
| Logic level | 3.3 V — relay modules for open sign, display accent, amp power, HVAC fan |

Use a dedicated Pi 4 at the rack or back office. Continuous BGM decode/streaming and filesystem playlists exceed Pico W RAM/CPU.

## Setup checklist

1. [ ] Install mqttpi on a **dedicated Pi 4** (Raspberry Pi OS).
2. [ ] Copy BGM files to `/opt/mqttpi/bgm/` (MP3/FLAC/OGG).
3. [ ] Copy SFX files to `/opt/mqttpi/sfx/store/` (tracks 01–03).
4. [ ] Wire I2S DAC or amp module on BCM 18–21; connect to 70 V amp or class-D module.
5. [ ] `cp examples/sites/store.yaml config.yaml`
6. [ ] `cp secrets.example.yaml secrets.yaml` — set broker host, credentials, and stream URLs.
7. [ ] Change `device.id` if `store-main` collides on the broker.
8. [ ] Wire `amp_power` relay if the amplifier needs a hardware enable.
9. [ ] Test stream control via MQTT before enabling `autoplay_on_boot`.
10. [ ] Verify entities in Home Assistant after the bridge publishes discovery payloads.

## Entities

| HA entity | GPIO | Role |
|-----------|------|------|
| `binary_sensor.front_door` | BCM 5 | Front door contact |
| `binary_sensor.stockroom_door` | BCM 6 | Stockroom door contact |
| `binary_sensor.motion_floor` | BCM 16 | Sales floor motion |
| `switch.open_sign` | BCM 17 | Open sign relay |
| `switch.display_accent` | BCM 22 | Window display accent |
| `switch.amp_power` | BCM 23 | Amplifier power relay |
| `switch.hvac_fan` | BCM 24 | HVAC fan |
| `number.display_dim` | BCM 12 (PWM) | Display dimmer (0–100%) |
| Background Music | I2S stream | BGM stream, volume, source select |
| SFX buttons ×3 | I2S | Door chime, closing soon, thank you |

## MQTT namespace

```
site/store/gpio/<alias>/state
site/store/gpio/<alias>/set
site/store/audio/stream/set
site/store/audio/volume/set
site/store/audio/source/set
site/store/sfx/play
site/store/status
```