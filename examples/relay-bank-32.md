# Relay bank — 32 channels (MCP23017 expanders)

32 relay outputs on a **Pico W** using **two MCP23017** I2C GPIO expanders. Each MCP23017 provides **16 GPIO** (8 on PORTA + 8 on PORTB); two chips yield 32 outputs while **GP0/GP1** carry I2C and the remaining native pins stay free.

For 16 relays on **native GPIO only** (no expanders), see [relay-bank-16](relay-bank-16.md).

## Why expanders?

A Pico W has ~23 usable GPIO after reserved pins. Thirty-two direct relay lines are not possible without external GPIO. The **MCP23017** adds 16 outputs per chip over I2C — set address jumpers for **0x20** and **0x21** on the two boards.

| Chip | I2C address | Relays | Expander pins |
|------|-------------|--------|---------------|
| MCP23017 #1 | `0x20` | `relay_01`–`relay_16` | 0–15 |
| MCP23017 #2 | `0x21` | `relay_17`–`relay_32` | 0–15 |

**Not** the MCP23008 — that part has only **8** GPIO. One MCP23017 replaces two MCP23008 boards for the same pin count.

## Wiring

| Signal | Pico W pin |
|--------|------------|
| I2C SDA | GP0 |
| I2C SCL | GP1 |
| 3.3 V / GND | Common with expander modules (logic only) |

- Set **A0/A1/A2** address jumpers: first module **0x20**, second **0x21**.
- Relay coil power is **separate** from Pico logic (typically 5 V or 12 V per module).
- Use flyback diodes or relay boards with built-in protection.

## MQTT / Home Assistant

- Topics: `mqttpi/relay-bank-32/gpio/relay_XX/state` and `.../set`
- Discovery: enabled — 32 `switch` entities under device **Relay Bank 32**
- Payloads: `ON` / `OFF` (retained state)

## Scaling

| Relays needed | Hardware |
|---------------|----------|
| 16 | 1× MCP23017 **or** native GP0–GP15 ([relay-bank-16](relay-bank-16.md)) |
| 32 | 2× MCP23017 (this example) |
| 48 | 3× MCP23017 @ 0x20, 0x21, 0x22 |
| 64 | 4× MCP23017 |

MCP23017 addresses are configurable via A0–A2 (eight devices per I2C bus: `0x20`–`0x27`).

## FAQ

**Can I mix native GPIO and expanders?**  
Yes — add `pins[]` with `bcm:` (native) and `expander:` entries in one config.

**Pi 4 instead of Pico W?**  
Change `board: pi4`, set `i2c.sda` / `i2c.scl` to your header pins (often GPIO2/GPIO3 on bus 1), and keep the same MCP23017 layout.

**Daemon status?**  
GPIO expander support is part of the mqttpi config contract; verify runtime support before production deploy.