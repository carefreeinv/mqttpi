# [maximum-gpio.yaml](maximum-gpio.yaml)

## Purpose / when to use

Empty **Home Assistant–ready** starter template for a **Raspberry Pi Pico W**. Use this when you want a clean slate: all peripheral buses and PWM are **disabled**, leaving the full GPIO pool free for your own `pins[]` entries.

Ideal for:

- New Pico W nodes before you know exact wiring
- Copy-paste base for custom projects
- Learning mqttpi config structure without example-specific pins

Entity types are inferred from `direction`: `output` → HA **switch**, `input` → **binary_sensor**, `analog_input` → **sensor**, `pwm_output` → **number**.

## Quick start

```bash
cp examples/maximum-gpio.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit device.id, mqtt.host, and secrets.yaml credentials
```

Flash or deploy the Pico W firmware/agent when available; until then this file documents the intended runtime contract.

## Board, profile, peripheral toggles

| Setting | Value |
|---------|-------|
| **Board** | `picow` (default) |
| **Profile** | `maximum_gpio` |
| **1-Wire** | `enabled: false` (reserved pin GP7) |
| **I2C** | `enabled: false` (SDA GP0, SCL GP1) |
| **SPI** | `enabled: false` (GP2–GP5) |
| **I2S** | `enabled: false` (GP16–GP19) |
| **PWM bank** | `enabled: false` (GP8–GP15) |
| **pins[]** | Empty — add your own |

Peripherals are **dynamic toggles**: set `enabled: true` on a bus only when you need it; reserved pins are documented in config even when disabled so you do not accidentally assign conflicting GPIO.

## GPIO pool / pin map

Pico W **maximum_gpio** with all peripherals off — **23 GPIO lines** available (GP0–GP22, GP26–GP28). ADC-capable pins are GP26–GP28.

| GPIO | Role (this example) | Notes |
|------|---------------------|-------|
| GP0–GP6 | **Free** | Safe for digital I/O when buses stay off |
| GP7 | 1-Wire (disabled) | Enable `buses.onewire` to use |
| GP8–GP15 | PWM bank (disabled) | Standard Pico W PWM pool; enable `pwm.enabled` |
| GP16–GP19 | I2S (disabled) | Audio / SFX when `buses.i2s` enabled |
| GP20–GP22 | **Free** | Digital I/O |
| GP26–GP28 | **Free** (ADC) | `analog_input` only; 0–3.3 V |

No pins are assigned in this example (`pins: []`).

## MQTT & HA entities expected

With an empty `pins[]` list, the node publishes **device discovery metadata** only (manufacturer, model, `device.id`). No switch, sensor, or number entities appear until you add pin entries.

Default topic layout (from mqttpi conventions):

| Entity type | State topic | Command topic |
|-------------|-------------|---------------|
| switch | `{base_topic}/gpio/{alias}/state` | `{base_topic}/gpio/{alias}/set` |
| binary_sensor | `{base_topic}/gpio/{alias}/state` | — |
| sensor (ADC) | `{base_topic}/gpio/{alias}/state` | — |
| number (PWM) | `{base_topic}/gpio/{alias}/state` | `{base_topic}/gpio/{alias}/set` |

**HA discovery** is on (`mqtt.homeassistant.discovery: true`). Discovery payloads use prefix `homeassistant`.

Example defaults from this file:

- `base_topic`: `mqttpi/pico-node-01`
- `client_id`: `mqttpi-pico-node-01`
- Device name: **Pico Node 01**

## Design decisions

- **Pico W default board** — Wi-Fi onboard; matches most mqttpi examples.
- **All peripherals disabled** — Maximizes GPIO headroom; avoids silent pin conflicts.
- **PWM pins GP8–GP15 listed even when off** — Documents the canonical Pico W PWM bank per mqttpi convention; enabling PWM does not require reshuffling other config.
- **HA discovery on by default** — Entities appear automatically in Home Assistant when the broker receives discovery messages; no manual `configuration.yaml` MQTT entries.
- **`secrets.yaml` separate** — Broker username/password live in gitignored secrets, merged at runtime onto `config.yaml`.
- **Empty `mqtt_aliases`** — Add alias remapping only when MQTT topic names must differ from internal `name` fields (see [garage-door.md](garage-door.md)).

## FAQ

**Q: Why are bus pins listed if the buses are disabled?**  
A: mqttpi configs document *default reservations* so enabling a bus later does not surprise you with pin conflicts. Disabled buses do not drive those pins.

**Q: How many pins can I actually use?**  
A: With `profile: maximum_gpio` and everything off, **23 pins** (GP0–GP22 and GP26–GP28). Enabling I2C, SPI, 1-Wire, I2S, or PWM removes pins from the free pool.

**Q: Do I need to change `profile` when I add pins?**  
A: Usually no. Stay on `maximum_gpio` until you enable sensor buses (`sensors`) or all peripherals (`full_peripherals`). See [sensors-i2c-onewire.md](sensors-i2c-onewire.md) and [full-peripherals.md](full-peripherals.md).

**Q: Where do MQTT credentials go?**  
A: In `secrets.yaml` at the repo root (`mqtt.username`, `mqtt.password`). Never commit real passwords in `config.yaml`.

**Q: Will Home Assistant see this node with no pins?**  
A: You may see a device shell after the agent connects and publishes discovery. Functional entities require at least one `pins[]` entry.

## Related examples

- [digital-in-out.md](digital-in-out.md) — First relay + button on GP0/GP1
- [home-assistant.md](home-assistant.md) — Reference for HA entity types and metadata
- [full-peripherals.md](full-peripherals.md) — Opposite extreme: all buses + PWM on
- [pi4-maximum-gpio.md](pi4-maximum-gpio.md) — Same idea on Raspberry Pi 4/5

## Implementation status

**Config-only.** This YAML defines the intended Pico W runtime contract. The mqttpi repo currently ships a working **BMS UART bridge** (`python3 -m mqttpi.bms.bridge`); GPIO/MQTT firmware for Pico W is not yet in-tree. Use this file to plan wiring and HA entities; validate against the agent when released.