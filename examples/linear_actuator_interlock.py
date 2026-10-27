#!/usr/bin/env python3
"""Run the mqttpi daemon with software interlocks for a reversible actuator.

* ``actuator_extend`` and ``actuator_retract`` are mutually exclusive: turning
  one ON while the other is ON is rejected (switch the active one OFF first).
* Extending is blocked while ``limit_extended`` is active; retracting is
  blocked while ``limit_retracted`` is active.

Rejected commands are logged and the true relay state is re-published, so Home
Assistant snaps back to what the hardware is doing.

    python3 examples/linear_actuator_interlock.py -c config.yaml -v
    python3 examples/linear_actuator_interlock.py -c config.yaml --mock-gpio -v

Software interlocks complement, not replace, hardware protection: use an
H-bridge / DPDT wiring that cannot short the supply even if both relays close.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running from a source checkout without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mqttpi.config import load_config  # noqa: E402
from mqttpi.daemon import Daemon  # noqa: E402
from mqttpi.gpio.commands import block_while, mutually_exclusive  # noqa: E402

EXTEND = "actuator_extend"
RETRACT = "actuator_retract"


def build_filters(cfg: dict) -> list:
    aliases = {str(p.get("alias")) for p in cfg.get("pins", [])}
    filters = [mutually_exclusive(EXTEND, RETRACT)]
    if "limit_extended" in aliases:
        filters.append(block_while(EXTEND, "limit_extended"))
    if "limit_retracted" in aliases:
        filters.append(block_while(RETRACT, "limit_retracted"))
    return filters


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-c", "--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("-s", "--secrets", type=Path, default=Path("secrets.yaml"))
    parser.add_argument("--mock-gpio", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    cfg = load_config(args.config, args.secrets if args.secrets.exists() else None)
    try:
        Daemon(cfg, mock_gpio=args.mock_gpio, command_filters=build_filters(cfg)).run()
    except (RuntimeError, ValueError) as exc:
        logging.getLogger("mqttpi").error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
