# House deployment

This guide walks through deploying the house site template on a dedicated **Raspberry Pi 4** node.

**Config:** [`examples/sites/house.yaml`](../examples/sites/house.yaml)

**Documentation:** [`examples/sites/house.md`](../examples/sites/house.md)

## Hardware

| Item | Notes |
|------|-------|
| Board | **Raspberry Pi 4** (dedicated node) |
| Config template | `examples/sites/house.yaml` |
| I2S DAC/amp | PCM5102 or MAX98357A for door chimes and alert SFX |
| Logic level | 3.3 V — use relay modules and opto-isolated inputs for HVAC and lighting |

Use a dedicated Pi 4 mounted in a utility closet or rack. I2S audio, filesystem access for WAV libraries, and concurrent MQTT + SFX playback exceed Pico W capabilities.

## Setup checklist

1. [ ] Install mqttpi on a **dedicated Pi 4** (Raspberry Pi OS).
2. [ ] Copy WAV files to `/opt/mqttpi/sfx/` (tracks 01–04 per config).
3. [ ] Wire I2S DAC on BCM 18–21 (BCLK, LRCK, DIN, DOUT).
4. [ ] `cp examples/sites/house.yaml config.yaml`
5. [ ] `cp secrets.example.yaml secrets.yaml` — set broker host and credentials.
6. [ ] Change `device.id` if `house-main` collides on the broker.
7. [ ] Wire door contacts, HVAC relays, and accent lighting through 3.3 V–safe interfaces.
8. [ ] Test with `python3 -m mqttpi --mock-gpio -v` before live GPIO.
9. [ ] Verify entities in Home Assistant after the bridge publishes discovery payloads.

## Entities

| HA entity | GPIO | Role |
|-----------|------|------|
| `binary_sensor.front_door` | BCM 5 | Front door contact |
| `binary_sensor.back_door` | BCM 6 | Back door contact |
| `binary_sensor.garage_door` | BCM 16 | Garage door contact |
| `switch.porch_accent` | BCM 17 | Porch accent lights |
| `switch.living_accent` | BCM 22 | Living room accent |
| `switch.hvac_heat` | BCM 23 | HVAC heat call |
| `switch.hvac_cool` | BCM 24 | HVAC cool call |
| `switch.hvac_fan` | BCM 25 | HVAC fan |
| `binary_sensor.water_leak` | BCM 27 | Water leak sensor |
| `number.dim_entry` | BCM 12 (PWM) | Entry dimmer (0–100%) |
| SFX buttons ×4 | I2S | Door chime, doorbell, alarm, garage alert |

## MQTT namespace

```
home/house/gpio/<alias>/state
home/house/gpio/<alias>/set
home/house/sfx/play
home/house/status
```