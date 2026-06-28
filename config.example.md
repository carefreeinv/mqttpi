# mqttpi — starter config

**Config file:** [`config.example.yaml`](config.example.yaml)

---

## Purpose

Minimal empty template for a new mqttpi node. All peripherals are **disabled** (`profile: maximum_gpio`) so every legal GPIO pin stays in the MQTT pool until you add `pins[]` entries or enable buses.

Copy this when you are building a custom layout from scratch rather than starting from a named example.

---

## Quick start

```bash
cp config.example.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# edit device.id, mqtt.host, secrets.yaml
```

For ready-made layouts, prefer [`examples/README.md`](examples/README.md) — each YAML has a matching `.md` with wiring, FAQ, and design notes.

---

## What you must change

| Field | Why |
|-------|-----|
| `device.id` | Unique per board on the broker |
| `mqtt.host` | Your MQTT broker IP/hostname |
| `secrets.yaml` → `mqtt.username` / `password` | Broker credentials |
| `device.ha.name` | Home Assistant device registry label |
| `pins[]` | Your actual wiring |

---

## Defaults (design decisions)

| Decision | Choice |
|----------|--------|
| Default board | **Pico W** |
| Default profile | **`maximum_gpio`** — all buses/PWM off |
| HA integration | Discovery **on**, payloads **ON/OFF**, state **retained** |
| Secrets | **`secrets.yaml`** merged at runtime (gitignored) |
| Topic root | `mqttpi/{device.id}` unless overridden |

---

## GPIO pool (Pico W, all peripherals off)

23 pins: GP0–6, GP7–22, GP26–28 (minus platform GP23–25).

Enable a bus or PWM in config to **reserve** pins — see any example doc for pin budget tables.

---

## FAQ

**Q: Should I edit `config.example.yaml` directly?**  
A: No. Copy to `config.yaml` (gitignored) and edit that.

**Q: Where do MQTT passwords go?**  
A: `secrets.yaml` only — never commit credentials.

**Q: How do entities appear in Home Assistant?**  
A: Enable MQTT integration with discovery; mqttpi publishes `homeassistant/*/config` on connect (when the daemon runs).

**Q: Is this file enough to run mqttpi today?**  
A: With an empty `pins[]` list, only the **BMS bridge** (`python3 -m mqttpi.bms.bridge`) runs from config today. GPIO/CAN/Victron daemons are still config contracts — use `examples/jbd-bms.yaml` for BMS.

---

## Related

- [examples/README.md](examples/README.md) — full example index
- [examples/maximum-gpio.md](examples/maximum-gpio.md) — same empty pool, documented
- [examples/jbd-bms.md](examples/jbd-bms.md) — only implemented protocol bridge so far