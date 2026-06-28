# 16 relay outputs (native Pico W GPIO)

**Config:** [`relay-bank-16.yaml`](relay-bank-16.yaml)

## Purpose

Drive **16 relays** using **only Pico W header GPIO** — no I2C MCP23017, no SPI expanders, no extra ICs. Fits panels that need a moderate channel count without wiring a separate bus.

## Quick start

```bash
cp examples/relay-bank-16.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

## Pin map (GP0–GP15)

| GP | Header (approx) | Alias | HA switch |
|----|-----------------|-------|-----------|
| 0 | Pin 1 | `relay_01` | Relay 01 |
| 1 | Pin 2 | `relay_02` | Relay 02 |
| 2 | Pin 4 | `relay_03` | Relay 03 |
| 3 | Pin 5 | `relay_04` | Relay 04 |
| 4 | Pin 6 | `relay_05` | Relay 05 |
| 5 | Pin 7 | `relay_06` | Relay 06 |
| 6 | Pin 9 | `relay_07` | Relay 07 |
| 7 | Pin 10 | `relay_08` | Relay 08 |
| 8 | Pin 11 | `relay_09` | Relay 09 |
| 9 | Pin 12 | `relay_10` | Relay 10 |
| 10 | Pin 14 | `relay_11` | Relay 11 |
| 11 | Pin 15 | `relay_12` | Relay 12 |
| 12 | Pin 16 | `relay_13` | Relay 13 |
| 13 | Pin 17 | `relay_14` | Relay 14 |
| 14 | Pin 19 | `relay_15` | Relay 15 |
| 15 | Pin 20 | `relay_16` | Relay 16 |

**Still free:** GP16–22, GP26–28 (7 pins) for inputs, ADC, or future use.

## Board & profile

| Setting | Value |
|---------|-------|
| Board | `picow` |
| Profile | `maximum_gpio` |
| Buses | All **disabled** |
| PWM | **Disabled** (GP8–15 used as digital outputs, not PWM bank) |

## Design decisions

| Decision | Rationale |
|----------|-----------|
| GP0–GP15 block | Maximum native relay count without expanders; contiguous numbering |
| `pwm.enabled: false` | PWM bank pins repurposed as digital outputs |
| `initial: false` | Safe boot — all relays off |
| No I2C/SPI | Zero extra parts; simplest BOM |

## MQTT / HA

```
mqttpi/relay-bank-16/gpio/relay_01/set … relay_16/set
```

Each channel is a HA **switch** under device **16-Channel Relay Bank**.

## FAQ

**Q: Why 16 and not 23?**  
A: 16 is a common relay board size (2×8, 16CH modules). Using GP0–15 leaves 7 pins for status inputs or analog.

**Q: Can I enable PWM on some pins too?**  
A: Not in this example — GP8–15 are relays here. Use [`pwm-bank.yaml`](pwm-bank.yaml) or [`multi-relay.yaml`](multi-relay.yaml) for mixed layouts.

**Q: How is this different from `relay-bank-32`?**  
A: **16 = native GPIO only.** [32 requires 2× MCP23017 expanders](relay-bank-32.md) on I2C (16 GPIO per chip).

**Q: Could I use one MCP23017 instead of native GPIO?**  
A: Yes — a single MCP23017 @ `0x20` gives 16 relay outputs on I2C (GP0/GP1) and frees GP0–GP15 for other uses. This example favors zero extra parts; see the scaling table in [relay-bank-32.md](relay-bank-32.md).

**Q: Implementation status?**  
A: Config contract — GPIO daemon not yet merged; BMS bridge is separate today.

## Related

- [`speaker-zones-8.md`](speaker-zones-8.md) — 8-zone distributed audio (subset of this layout)
- [`multi-relay.md`](multi-relay.md) — 4 relays (minimal)
- [`relay-bank-32.md`](relay-bank-32.md) — 32 relays with I2C expanders
- [`maximum-gpio.md`](maximum-gpio.md) — full 23-pin pool explained

## Wiring caution

Use **3.3 V–compatible relay modules** (logic inputs) or N-channel MOSFET per channel. Do not hang relay coil current on the Pico pin.