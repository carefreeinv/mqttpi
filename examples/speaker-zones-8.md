# 8-zone speaker control (native Pico W GPIO)

**Config:** [`speaker-zones-8.yaml`](speaker-zones-8.yaml)

## Purpose

Control **8 distributed-audio zones** from a Pico W using **relay or opto-isolator outputs** on **GP0–GP7**. Each GPIO line typically triggers one zone on a multi-room amplifier (Russound, Monoprice, HTD, Niles, etc.) or switches a local zone relay module.

Derived from [`relay-bank-16`](relay-bank-16.md) — same native-GPIO pattern, but only eight channels with zone-oriented naming and HA labels.

## Quick start

```bash
cp examples/speaker-zones-8.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

## Pin map (GP0–GP7)

| GP | Header (approx) | Alias | HA switch |
|----|-----------------|-------|-----------|
| 0 | Pin 1 | `zone_01` | Speaker Zone 1 |
| 1 | Pin 2 | `zone_02` | Speaker Zone 2 |
| 2 | Pin 4 | `zone_03` | Speaker Zone 3 |
| 3 | Pin 5 | `zone_04` | Speaker Zone 4 |
| 4 | Pin 6 | `zone_05` | Speaker Zone 5 |
| 5 | Pin 7 | `zone_06` | Speaker Zone 6 |
| 6 | Pin 9 | `zone_07` | Speaker Zone 7 |
| 7 | Pin 10 | `zone_08` | Speaker Zone 8 |

**Still free:** GP8–GP15 (PWM bank), GP16–22, GP26–GP28 — room for status LEDs, IR remote sense, or a future I2S node on another board.

## Board & profile

| Setting | Value |
|---------|-------|
| Board | `picow` |
| Profile | `maximum_gpio` |
| Buses | All **disabled** |
| PWM | **Disabled** (GP8–15 free; not used for zones here) |

## Design decisions

| Decision | Rationale |
|----------|-----------|
| GP0–GP7 only | Eight zones is a common whole-home audio layout; leaves 15+ pins free |
| `initial: false` | Safe boot — all zones off until HA/MQTT commands |
| Relay/optocoupler outputs | Amplifier zone triggers are low-current logic; isolate from speaker power |
| No I2S on this node | Zone **enable** only; source selection and playback stay on amp or media server |
| Zone aliases | `zone_01`–`zone_08` map cleanly to HA room automations |

## Typical wiring

```
Pico GPn ──► relay module INn ──► amplifier ZONE TRIGGER n (or 12 V zone relay coil)
```

- Use **3.3 V–compatible relay boards** or NPN/MOSFET drivers per channel.
- Many amps expect a **momentary or latched closure to ground** — check your amp manual; add a diode if driving inductive coils.
- **Speaker power and line-level audio** do not pass through the Pico; only low-voltage trigger lines.

## MQTT / Home Assistant

```
mqttpi/speaker-zones-8/gpio/zone_01/set … zone_08/set
mqttpi/speaker-zones-8/gpio/zone_01/state … zone_08/state
```

Each zone is a HA **switch** under device **8-Zone Speaker Controller**. Pair with `media_player` automations: turn zone ON, then start playback on your amp or streaming source.

Rename zones in `pins[].ha.name` to match rooms (e.g. `"Kitchen Speakers"`).

## FAQ

**Q: Why not use I2S on this Pico for audio?**  
A: Zone control is digital enable/disable. Playback usually lives on the amplifier, a Pi streamer, or [`house.yaml`](sites/house.yaml) / [`club.yaml`](sites/club.yaml) I2S SFX nodes. Keeping this node GPIO-only avoids bus conflicts and fits a small enclosure at the amp rack.

**Q: Can I add more than 8 zones?**  
A: Use [`relay-bank-16.md`](relay-bank-16.md) (16 native relays) or [`relay-bank-32.md`](relay-bank-32.md) (32 via MCP23017). Copy zone naming from this example.

**Q: Momentary vs latching triggers?**  
A: This config uses **latched** outputs (ON/OFF retained). For momentary pulse amps, add a HA automation or firmware pulse helper when the GPIO daemon supports it.

**Q: Implementation status?**  
A: Config contract — GPIO daemon not yet merged; BMS bridge is separate today.

## Related

- [`relay-bank-16.md`](relay-bank-16.md) — same GPIO pattern, 16 generic relays
- [`multi-relay.md`](multi-relay.md) — 4-channel minimal relay example
- [`sites/house.md`](sites/house.md) — residential template with I2S door chimes
- [`sites/club.md`](sites/club.md) — venue lighting + I2S announcements