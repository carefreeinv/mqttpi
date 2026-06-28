# Level accelerometer — I2C pitch/roll for RV / trailer

## Purpose

Expose **pitch**, **roll**, **combined deviation**, and a binary **Level OK** indicator for RVs, trailers, skoolies, and cargo rigs. Uses an I2C accelerometer/IMU mounted flat on the floor plane so Home Assistant can show how level the coach is before deploying slides, jacks, or appliances.

Standalone reference config — pair with any site template or run on a dedicated leveling node.

## Quick start

```bash
cp examples/level-accelerometer.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit mqtt.host, device.id, I2C address if needed
# Flash/build mqttpi firmware for Pico W (when runtime supports sensors.level)
```

After boot on **level pavement**, trigger calibration:

```bash
mosquitto_pub -h 192.168.1.50 -t mobile/level-node-01/level/calibrate -m ""
```

Entities appear via MQTT discovery under device **Vehicle Level**.

## Hardware

| Item | Spec |
|------|------|
| **Board** | Raspberry Pi Pico W (`board: picow`, `profile: sensors`) |
| **Sensor** | **MPU6050** @ `0x68` (default) or **ADXL345** @ `0x53` |
| **Bus** | I2C0 — SDA **GP0**, SCL **GP1** |
| **Mount** | Chip package flat on floor plane, X/Y aligned with vehicle axes |
| **Power** | 3.3 V from Pico; common GND |

### Pin budget (this example)

| Function | GPIO |
|----------|------|
| I2C SDA | GP0 |
| I2C SCL | GP1 |
| PWM bank (disabled) | GP8–15 reserved by profile |

## Bus wiring

```
Pico W          MPU6050 / ADXL345
──────          ─────────────────
GP0 (SDA) ───── SDA
GP1 (SCL) ───── SCL
3V3 (OUT) ───── VCC
GND       ───── GND
```

- Keep I2C leads short; add **4.7 kΩ** pull-ups on SDA/SCL if the module has none.
- ADXL345: set `sensors.level.chip: adxl345` and `address: 0x53` in config.
- Avoid mounting on sprung insulation or flexible panels — attach to structural floor.

## MQTT / Home Assistant topics

Default `base_topic`: `mobile/level-node-01`

### Published state (retained, ~2 s interval)

| Alias | Topic pattern | HA type | Unit |
|-------|---------------|---------|------|
| `level_pitch` | `{base_topic}/sensors/level_pitch/state` | sensor | ° |
| `level_roll` | `{base_topic}/sensors/level_roll/state` | sensor | ° |
| `level_deviation` | `{base_topic}/sensors/level_deviation/state` | sensor | ° (max abs of pitch/roll) |
| `is_level` | `{base_topic}/sensors/is_level/state` | binary_sensor | ON/OFF |

Threshold for **Level OK**: `1.5°` (`threshold_deg` in config).

### Command

| Topic | Action |
|-------|--------|
| `{base_topic}/level/calibrate` | Zero pitch/roll against current orientation (`calibration.mode: on_boot` also runs at startup) |

### Home Assistant discovery

```
homeassistant/sensor/{device_id}_level_pitch/config
homeassistant/sensor/{device_id}_level_roll/config
homeassistant/sensor/{device_id}_level_deviation/config
homeassistant/binary_sensor/{device_id}_is_level/config
```

Device block: **Vehicle Level** (`device.ha.name`).

## Design decisions

1. **Floor-plane mount** — Pitch/roll are computed assuming the PCB lies in the vehicle floor plane; roof-mount IMUs would need a different `mount` transform.
2. **On-boot + MQTT calibrate** — Lets you re-zero after jack adjustments without reflashing.
3. **`max_abs` deviation** — Single number for dashboards (“how far off level?”) instead of reading two angles.
4. **1.5° binary threshold** — Practical default for RV slide-out safety; tighten for precision leveling apps.
5. **I2C0 on GP0/GP1** — Matches the `sensors` profile pin map used across mqttpi examples.
6. **2 s publish interval** — Low enough for UI refresh, light enough for battery-powered nodes.

## FAQ

**Q: MPU6050 or ADXL345?**  
A: MPU6050 is the default (gyro unused for level-only). ADXL345 is a good alternative if you already stock it — update `chip` and `address` in YAML.

**Q: Readings drift after I drive onto blocks — is that normal?**  
A: Accelerometers measure gravity vector relative to the chip. Re-calibrate on the final parked attitude via the calibrate topic.

**Q: Can I use this while driving?**  
A: You will get motion artifacts. Use `is_level` only when stationary.

**Q: Does this replace bubble levels or jack control?**  
A: No — it is a telemetry input for HA dashboards and automations (warnings, voice prompts). It does not drive hydraulic jacks.

**Q: Why Pico W instead of Pi 4?**  
A: This example targets a small wireless node near the floor. A Pi 4 with I2C hat works if you prefer Linux — adapt `board` and I2C bus settings.

## Related examples

| Example | Relationship |
|---------|--------------|
| [`sites/rv.yaml`](sites/rv.yaml) | Full RV GPIO + coach sensors |
| [`sites/trailer.yaml`](sites/trailer.yaml) | Trailer-focused site template |
| [`sites/skoolie.yaml`](sites/skoolie.yaml) | Skoolie coach layout |
| [`sensors-i2c-onewire.yaml`](sensors-i2c-onewire.yaml) | General I2C bus reference |
| [`tpms.yaml`](tpms.yaml) | Another mobile safety sensor |

## Implementation status

| Component | Status |
|-----------|--------|
| `examples/level-accelerometer.yaml` | **Config contract** — schema reference |
| Pico W `sensors.level` runtime | **Not implemented** — YAML defines intended MQTT/HA mapping |
| MPU6050 / ADXL345 driver | **Planned** — firmware TBD |

Unlike [`jbd-bms.md`](jbd-bms.md), there is **no shipped Python or firmware decoder** yet. Topic names and HA entities describe the target contract for implementers.