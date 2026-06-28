# 32 relay outputs (Pico W + MCP23017)

**Config:** [`relay-bank-32.yaml`](relay-bank-32.yaml)

## Purpose

Control **up to 32 relay channels** from a Pico W when native GPIO (max ~23) is not enough. Uses **four MCP23017** I2C GPIO expanders (8 outputs each) at addresses `0x20`–`0x23`.

## Can Pico W do 32 relays alone?

**No.** Native GPIO tops out at ~23 pins. **32 relays requires I2C expanders** (or a Pi 4 + more expanders). This example documents the supported approach.

## Quick start

```bash
cp examples/relay-bank-32.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

Wire MCP23017 modules to **I2C0: GP0 (SDA), GP1 (SCL)**. Set each module's address strap to 0x20–0x23.

## Hardware

| Part | Qty | Notes |
|------|-----|-------|
| Pico W | 1 | MQTT over Wi-Fi |
| MCP23017 breakout | 4 | 3.3 V, addresses 0x20–0x23 |
| Relay modules | 32 | Driven via transistor/MOSFET per channel |
| Pull-ups | — | Often on breakout boards (4.7 kΩ on SDA/SCL) |

## MQTT / HA

Each `relay_01` … `relay_32` becomes a HA **switch** under device **32-Channel Relay Bank**.

Topics: `mqttpi/relay-bank-32/gpio/relay_NN/set`

## Design decisions

| Decision | Rationale |
|----------|-----------|
| I2C not SPI | Only 2 pins; leaves native GPIO and PWM bank free |
| 4× MCP23017 | Common, cheap, well-documented; 8 bits per chip |
| `profile: sensors` | Reserves I2C; disables unrelated buses |
| All outputs `initial: false` | Safe boot — relays off |

## FAQ

**Q: Can I use fewer than 32 relays?**  
A: Yes — remove unused `pins[]` entries and omit unpopulated MCP23017 chips.

**Q: What if two chips share an address?**  
A: I2C collision — set address jumpers uniquely (0x20–0x27 available on most boards).

**Q: Will expander toggling be fast enough?**  
A: I2C at 100–400 kHz is fine for relays (ms-scale); not for high-frequency PWM.

**Q: Is this implemented in code yet?**  
A: **Config contract only** — MCP23017 driver pending in main mqttpi daemon.

## Related

- [`multi-relay.md`](multi-relay.md) — 4 native GPIO relays
- [`relay-bank-32.yaml`](relay-bank-32.yaml)
- [`sites/cargo-trailer.md`](sites/cargo-trailer.md) — first field project (fewer channels)

## Implementation status

**Config only.** Requires future `expanders.mcp23017` support in runtime.