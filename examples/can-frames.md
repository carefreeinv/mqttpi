# [can-frames.yaml](can-frames.yaml)

## Purpose / when to use

Turn broadcast CAN frames into Home Assistant **sensor** entities on a Raspberry Pi (Linux SocketCAN). Use it for battery monitors, engine ECUs (J1939-style PGNs), switch panels, or any device whose CAN frame layout you know. It is **read-only**: mqttpi never transmits.

## Quick start

1. Add a CAN interface:
   - **MCP2515 HAT:** add `dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25` to `/boot/firmware/config.txt`, using your HAT's crystal and INT pin. Also enable SPI.
   - **USB-CAN adapter:** usually plug-and-play (`gs_usb`).
2. Bring it up: `sudo ip link set can0 up type can bitrate 250000 restart-ms 100`. mqttpi does not configure the interface.
3. Look at the traffic: `sudo apt install can-utils && candump can0`.
4. Run it:
   ```bash
   cp examples/can-frames.yaml config.yaml
   python3 -m mqttpi -c config.yaml -v
   ```

Test without hardware on a virtual bus:

```bash
sudo modprobe vcan && sudo ip link add dev vcan0 type vcan && sudo ip link set up vcan0
# set interface: vcan0 in config.yaml, run mqttpi, then:
cansend vcan0 356#E803F6FF2C010000      # 10.00 V, -1.0 A, 30.0 °C
```

## Frame mapping (`type: can_frame`)

| Key | Meaning |
|-----|---------|
| `interface` | SocketCAN interface (default `can0`) |
| `id` | Arbitration id. Ids above 0x7FF are extended (29-bit) unless `extended:` is set |
| `pgn` | Instead of `id`: match 29-bit frames by J1939-style PGN, with any priority and source |
| `source_address` | With `pgn`: only frames from this sender |
| `match` | `{byte_index: value}`. Every listed data byte must equal its value (e.g. an instance byte) |
| `max_age_s` | Optional. If no matching frame arrives for this long, the read fails, and after `stale_after_s` the entity goes offline |
| `readings.<key>.start_byte` | 0–7 |
| `readings.<key>.length` | 1–8 bytes (default 1) |
| `readings.<key>.byte_order` | `little` (default) or `big` |
| `readings.<key>.signed` | Two's complement (default false) |
| `readings.<key>.bit` | 0–7: a single bit of `start_byte`, published as 0/1 |
| `readings.<key>.scale`, `offset` | value = raw × scale + offset |
| `readings.<key>.not_available` | Raw values to skip. Default: all bits set (0xFF, 0xFFFF, …), the J1939 "not available" value |

Readings use the shared sensor entities ([daemon.md](../daemon.md#sensors-numeric-readings)). State goes to `{base_topic}/sensors/<alias>/state`, the latest frame is published every `publish.interval_ms`, and the entities get HA discovery.

## Notes

- **Bus-off.** A wrong bitrate, a missing termination (120 Ω at both ends) or no other node to ACK puts the controller in bus-off. mqttpi logs `bus-off`, and with `restart-ms 100` the kernel recovers by itself.
- **Interface down or unplugged.** mqttpi logs it once and reopens the interface with backoff. Other subsystems keep running.
- **RV-C and other protocol decoders** (`examples/can-rvc.yaml`, top-level `can:`) are documented contracts that are not decoded yet. Until they are, map the frames you need with `can_frame`.
