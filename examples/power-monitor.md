# [power-monitor.yaml](power-monitor.yaml)

## Purpose / when to use

Measure the voltage, current and power of a DC supply or battery bank with an INA219 or INA226 current/voltage monitor on I2C. Examples: an RV house battery, a workshop 12 V bus, or a solar charge input on an unattended Pi node.

> **Status: schema only.** The `power_monitor` types (`ina219`, `ina226`) are specified here ahead of their driver. Until the driver lands, the daemon loads this config, logs `no driver for type 'ina219' yet — skipped`, and keeps running the other sensors.

## Config contract

| Key | Required | Meaning |
|-----|----------|---------|
| `type` | yes | `ina219` or `ina226` |
| `bus` | no (`1`) | Linux I2C bus number (`/dev/i2c-N`) |
| `address` | no (`0x40`) | 7-bit address, 0x40–0x4F |
| `shunt_ohms` | yes | Shunt resistor value (common breakout boards: 0.1 Ω) |
| `max_current_a` | yes | Expected maximum current. It sets the calibration register and the current LSB |
| `bus_voltage_range` | no (`32`) | INA219 only: 16 or 32 V |
| `averaging` | no (`1`) | INA226 only: 1, 4, 16, 64, 128, 256, 512 or 1024 samples |
| `readings` | no | `voltage` (V, bus voltage), `current` (A, signed), `power` (W). All three by default |

Readings publish through the shared sensor entities: `{base_topic}/sensors/<alias>/state`, with HA `sensor` discovery. See [daemon.md](../daemon.md#sensors-numeric-readings).

## Wiring

- VCC → 3.3 V, GND → GND, SDA → GPIO 2, SCL → GPIO 3.
- The shunt goes in series with the load on the **high side** (VIN+ toward the supply, VIN− toward the load).
- Common ground between the measured circuit and the Pi.
- Check the address with `i2cdetect -y 1`.

## FAQ

**Q: Why is `max_current_a` required?**
A: The chips compute current from a calibration value that depends on the shunt and the current range. A small range gives finer resolution, and a range set too small clips.

**Q: Can I measure more than 26 V (INA219) or 36 V (INA226)?**
A: No. The bus input is limited to those voltages; use a module designed for higher voltages.
