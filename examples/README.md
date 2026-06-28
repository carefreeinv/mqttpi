# mqttpi example configs

Each `*.yaml` example has a matching `*.md` doc with purpose, wiring, decisions, and FAQ.

## Setup (all examples)

```bash
cp examples/<name>.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# edit device.id, mqtt.host, secrets.yaml
```

Runtime merges `secrets.yaml` onto `config.yaml`. Home Assistant MQTT **discovery is on by default**.

## Generic examples

| Config | Doc | Summary |
|--------|-----|---------|
| `maximum-gpio.yaml` | [maximum-gpio.md](maximum-gpio.md) | Empty Pico W, all peripherals off |
| `digital-in-out.yaml` | [digital-in-out.md](digital-in-out.md) | 1 relay + 1 button |
| `multi-relay.yaml` | [multi-relay.md](multi-relay.md) | 4 relay outputs |
| `relay-bank-16.yaml` | [relay-bank-16.md](relay-bank-16.md) | 16 relays, native GPIO only |
| `speaker-zones-8.yaml` | [speaker-zones-8.md](speaker-zones-8.md) | 8-zone speaker amp triggers (GP0–7) |
| `pwm-bank.yaml` | [pwm-bank.md](pwm-bank.md) | 4 PWM channels (GP8–11) |
| `servo-controller.yaml` | [servo-controller.md](servo-controller.md) | 4× 50 Hz servos |
| `analog-inputs.yaml` | [analog-inputs.md](analog-inputs.md) | ADC on GP26–28 |
| `garage-door.yaml` | [garage-door.md](garage-door.md) | Relay + reed + button |
| `home-assistant.yaml` | [home-assistant.md](home-assistant.md) | HA reference entities |
| `sensors-i2c-onewire.yaml` | [sensors-i2c-onewire.md](sensors-i2c-onewire.md) | I2C + 1-Wire enabled |
| `full-peripherals.yaml` | [full-peripherals.md](full-peripherals.md) | All buses + PWM on |
| `pi4-maximum-gpio.yaml` | [pi4-maximum-gpio.md](pi4-maximum-gpio.md) | Pi 4, 26 GPIO free |
| `pi4-pwm-relay.yaml` | [pi4-pwm-relay.md](pi4-pwm-relay.md) | Pi 4 HW PWM + relay |
| `relay-bank-32.yaml` | [relay-bank-32.md](relay-bank-32.md) | 32 relays via 2× MCP23017 I2C (16 GPIO/chip) |
| `robot.yaml` | [robot.md](robot.md) | Differential-drive rover |

## Protocol & sensor examples

| Config | Doc | Summary |
|--------|-----|---------|
| `jbd-bms.yaml` | [jbd-bms.md](jbd-bms.md) | JBD BMS UART (Pi, from bms0) |
| `level-accelerometer.yaml` | [level-accelerometer.md](level-accelerometer.md) | I2C MPU6050 level |
| `tpms.yaml` | [tpms.md](tpms.md) | Tire pressure (UART receiver) |
| `can-vehicle.yaml` | [can-vehicle.md](can-vehicle.md) | OBD-II read @ 500k |
| `can-rvc.yaml` | [can-rvc.md](can-rvc.md) | RV-C read/write @ 250k |
| `can-can2040.yaml` | [can-can2040.md](can-can2040.md) | PIO software CAN |
| `victron-vedirect.yaml` | [victron-vedirect.md](victron-vedirect.md) | Victron UART shunt/solar |
| `victron-vecan.yaml` | [victron-vecan.md](victron-vecan.md) | Victron VE.Can NMEA2000 |

## Site templates (`sites/`)

| Config | Doc |
|--------|-----|
| [house.yaml](sites/house.yaml) | [house.md](sites/house.md) |
| [workshop.yaml](sites/workshop.yaml) | [workshop.md](sites/workshop.md) |
| [club.yaml](sites/club.yaml) | [club.md](sites/club.md) |
| [store.yaml](sites/store.yaml) | [store.md](sites/store.md) |
| [rv.yaml](sites/rv.yaml) | [rv.md](sites/rv.md) |
| [motorhome.yaml](sites/motorhome.yaml) | [motorhome.md](sites/motorhome.md) |
| [skoolie.yaml](sites/skoolie.yaml) | [skoolie.md](sites/skoolie.md) |
| [skoolie-bms.yaml](sites/skoolie-bms.yaml) | [skoolie-bms.md](sites/skoolie-bms.md) |
| [trailer.yaml](sites/trailer.yaml) | [trailer.md](sites/trailer.md) |
| [cargo-trailer.yaml](sites/cargo-trailer.yaml) | [cargo-trailer.md](sites/cargo-trailer.md) |
| [snowmobile-trailer.yaml](sites/snowmobile-trailer.yaml) | [snowmobile-trailer.md](sites/snowmobile-trailer.md) |
| [cargo-trailer-workshop.yaml](sites/cargo-trailer-workshop.yaml) | [cargo-trailer-workshop.md](sites/cargo-trailer-workshop.md) |
| [camper-top.yaml](sites/camper-top.yaml) | [camper-top.md](sites/camper-top.md) |
| [semi.yaml](sites/semi.yaml) | [semi.md](sites/semi.md) |
| [rv-victron.yaml](sites/rv-victron.yaml) | [rv-victron.md](sites/rv-victron.md) |

## First project

| Guide | Config |
|-------|--------|
| [projects/cargo-trailer/README.md](../projects/cargo-trailer/README.md) | [sites/cargo-trailer.yaml](sites/cargo-trailer.yaml) |

Not registered on the central broker yet — deploy on a **dedicated Pico W**.