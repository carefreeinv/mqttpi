# Pi Zero W / Zero 2 W relay node

[`pizero-relays.yaml`](pizero-relays.yaml): four relay outputs and two contact inputs on a Raspberry Pi Zero W or Zero 2 W (`device.board: pizero`). It suits small, low-power unattended Pi nodes.

## Board profile

| | Pi Zero W | Pi Zero 2 W |
|---|---|---|
| GPIO (BCM) | 0–27 on the 40-pin header | same |
| Hardware PWM | GPIO 12, 13, 18, 19 (two channels) | same |
| ADC | none — use an external converter (e.g. ADS1115 on I2C) | none |
| CPU | single-core ARMv6 (1 GHz) | quad-core ARMv8 (1 GHz) |
| Wi-Fi | 2.4 GHz only | 2.4 GHz only |
| GPIO library | `RPi.GPIO` (`python3-rpi.gpio`) | same |

mqttpi validates `pins[]` against the board at startup. It rejects GPIO numbers that do not exist (for example `pin: 30`), a pin used twice, and a pin claimed by an enabled bus (`buses.i2c.sda`, `buses.onewire.pin`, or GPIO 14/15 when `bms.port` is `/dev/serial0`). Using GPIO 0/1 (HAT ID EEPROM) logs a warning.

## Wiring

| GPIO | Alias | Notes |
|------|-------|-------|
| 17, 27, 22, 23 | `relay_1`–`relay_4` | Relay board IN1–IN4. Set `invert: true` for active-low boards |
| 24, 25 | `contact_1`, `contact_2` | Switch to GND; internal pull-up, `invert: true` → closed = ON |

Power relay coils from the relay board's supply, not from the Zero's 3.3 V pin.

## Run

```bash
sudo apt install -y python3-venv python3-rpi.gpio git
git clone https://github.com/carefreeinv/mqttpi.git && cd mqttpi
python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements.txt
cp examples/pizero-relays.yaml config.yaml    # set mqtt.host, device.id
.venv/bin/python -m mqttpi -c config.yaml --mock-gpio -v   # dry run, no hardware
.venv/bin/python -m mqttpi -c config.yaml -v               # real GPIO (user in the gpio group)
```

## Tips for the Zero W

- `pip install` on the single-core Zero W is slow; `--system-site-packages` reuses Debian's `python3-rpi.gpio` and `python3-yaml`.
- A lower `mqtt.keepalive` (here 30 s) detects Wi-Fi drop-outs sooner; the daemon reconnects in the background.
- Disable Wi-Fi power saving if the node drops off the network: `sudo iw wlan0 set power_save off`.

## Tested

The unit tests cover the board profile and validation. Bench testing on real Zero W / Zero 2 W hardware (outputs, inputs, 24 h CPU and memory) is **pending**. Results will be recorded here.
