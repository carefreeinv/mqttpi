# [servo-controller.yaml](servo-controller.yaml)

## Purpose / when to use

Four **hobby servo** channels on **GP8–GP11** at **50 Hz**, controlled from Home Assistant as **number** entities (0–100 % duty mapped to servo position).

Use for:

- Pan/tilt camera mounts
- Gripper or latch mechanisms
- Small robotics prototypes
- Any RC-style servo needing ~1–2 ms pulse widths within a 20 ms frame

For LED dimming or PC fans, use [pwm-bank.md](pwm-bank.md) instead (1 kHz / 25 kHz).

## Quick start

```bash
cp examples/servo-controller.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit device.id, mqtt.host, secrets.yaml
```

Power servos from a **separate 5 V supply**; connect grounds together with the Pico. Signal wires go to GP8–GP11.

## Board, profile, peripheral toggles

| Setting | Value |
|---------|-------|
| **Board** | `picow` |
| **Profile** | `pwm_only` |
| **PWM** | **`enabled: true`** — bank GP8–GP15 |
| **1-Wire / I2C / SPI / I2S** | all off |

## GPIO pool / pin map

| GPIO | Alias | Freq | Initial duty | HA name | Notes |
|------|-------|------|--------------|---------|-------|
| GP8 | `servo_pan` | 50 Hz | 7% | Servo Pan | ~neutral for many servos |
| GP9 | `servo_tilt` | 50 Hz | 7% | Servo Tilt | ~neutral |
| GP10 | `servo_grip` | 50 Hz | 0% | Servo Grip | closed/min at boot |
| GP11 | `servo_aux` | 50 Hz | 0% | Servo Aux | min at boot |
| GP12–GP15 | — | PWM spare | — | — | Extend config here |
| GP0–GP7, GP16–GP22 | — | free / reserves | — | — | — |
| GP26–GP28 | — | ADC | — | — | Not for servos |

## MQTT & HA entities expected

| Entity | Type | Range | Topics under `mqttpi/servo-01` |
|--------|------|-------|--------------------------------|
| `number.servo_pan` | number | 0–100, step 1 | `gpio/servo_pan/state`, `gpio/servo_pan/set` |
| `number.servo_tilt` | number | 0–100, step 1 | `gpio/servo_tilt/...` |
| `number.servo_grip` | number | 0–100, step 1 | `gpio/servo_grip/...` |
| `number.servo_aux` | number | 0–100, step 1 | `gpio/servo_aux/...` |

No `unit_of_measurement` in config—HA shows raw 0–100; calibrate to degrees in automations if needed.

## Design decisions

- **50 Hz on all channels** — Standard analog servo frame rate; distinct from [pwm-bank.md](pwm-bank.md) LED/fan frequencies.
- **`initial_duty: 7` on pan/tilt** — Approximate center position at boot to avoid slamming to a rail on power-up (servo-dependent—tune per hardware).
- **`initial_duty: 0` on grip/aux** — “Closed” or minimum safe position for end-effectors.
- **GP8–GP11** — Same PWM bank convention as other Pico W PWM examples; keeps servo wiring away from GP0–GP3 relay territory.
- **HA number, not cover** — mqttpi maps `pwm_output` to granular sliders; use automations for scripted sweeps.

## FAQ

**Q: How do I convert 0–100 % to degrees?**  
A: Servos are non-linear. Measure duty at your mechanical min/max, then map in HA (`template` number or `calibration` helpers). This config intentionally stays generic.

**Q: Why 7 % initial duty for pan/tilt?**  
A: Many servos center near ~7 % duty (≈1.5 ms pulse). Replace with your calibrated neutral after testing.

**Q: Can I run servos and relays on one board?**  
A: Yes if relays use GP0–GP7 and servos stay on GP8–GP11. Do not enable conflicting buses on shared pins.

**Q: My servo jitters at rest.**  
A: Use a powered servo rail, add a capacitor near the servo, and avoid sharing USB power with motors. Software deadband may come with the future agent.

**Q: Continuous rotation servo?**  
A: Same 50 Hz PWM; map 0–100 to speed/direction with different duty centers—calibrate in HA.

## Related examples

- [pwm-bank.md](pwm-bank.md) — Non-servo PWM (1 kHz / 25 kHz)
- [pi4-pwm-relay.md](pi4-pwm-relay.md) — Pi 4 PWM + relay combo
- [digital-in-out.md](digital-in-out.md) — Simple GPIO when servos not needed
- [full-peripherals.md](full-peripherals.md) — PWM enabled alongside buses

## Implementation status

**Config-only.** Servo timing and HA discovery schema are defined; Pico W firmware to generate 50 Hz PWM is not yet in-tree. The **JBD BMS bridge** is the implemented MQTT component in this repo.