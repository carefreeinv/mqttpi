"""Home Assistant MQTT discovery topic layouts.

Home Assistant accepts ``<prefix>/<component>/[<node_id>/]<object_id>/config``.

* **flat** (default, unchanged): ``<prefix>/<component>/<device_id>_<object_id>/config``
* **node** (opt-in, ``mqtt.homeassistant.discovery_node_id``):
  ``<prefix>/<component>/<node_id>/<object_id>/config`` so a broker ACL can
  restrict each node to ``<prefix>/+/<node_id>/#``.

``unique_id`` values never depend on the layout, so Home Assistant keeps entity
ids and history when an install switches layouts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

DEFAULT_DISCOVERY_PREFIX = "homeassistant"
_NODE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class DiscoveryLayout:
    prefix: str = DEFAULT_DISCOVERY_PREFIX
    node_id: Optional[str] = None  # None = flat (legacy) layout
    clear_legacy: bool = True  # node layout: empty the flat-layout topics first

    @property
    def uses_node_id(self) -> bool:
        return self.node_id is not None

    def flat_topic(self, component: str, device_id: str, object_id: str) -> str:
        return f"{self.prefix}/{component}/{device_id}_{object_id}/config"

    def topic(self, component: str, device_id: str, object_id: str) -> str:
        """Discovery config topic for one entity of ``device_id``."""
        if self.node_id is None:
            return self.flat_topic(component, device_id, object_id)
        # The node's own entities use the bare object id; another logical
        # device on the same node (e.g. a BMS) keeps its device prefix.
        obj = object_id if sanitize_node_id(device_id) == self.node_id else f"{device_id}_{object_id}"
        return f"{self.prefix}/{component}/{self.node_id}/{obj}/config"

    def stale_topics(self, component: str, device_id: str, object_id: str) -> List[str]:
        """Old-layout topics to clear (empty retained payload) before publishing."""
        if self.node_id is None or not self.clear_legacy:
            return []
        return [self.flat_topic(component, device_id, object_id)]


def sanitize_node_id(value: str) -> str:
    """Map a device id onto HA's node_id alphabet ``[A-Za-z0-9_-]``."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)


def parse_discovery_layout(cfg: Dict[str, Any]) -> DiscoveryLayout:
    """Layout from ``mqtt.homeassistant`` in a full config.

    ``discovery_node_id``: ``false`` / unset (flat), ``true`` (use ``device.id``),
    or an explicit node id string. ``discovery_clear_legacy`` (default ``true``)
    clears the flat-layout retained configs when the node layout is on.
    """
    ha = cfg.get("mqtt", {}).get("homeassistant", {}) or {}
    prefix = str(ha.get("discovery_prefix", DEFAULT_DISCOVERY_PREFIX)).rstrip("/")
    raw = ha.get("discovery_node_id", False)
    clear = bool(ha.get("discovery_clear_legacy", True))
    if raw is None or raw is False:
        return DiscoveryLayout(prefix=prefix, clear_legacy=clear)
    if raw is True:
        node_id = sanitize_node_id(str(cfg.get("device", {}).get("id", "mqttpi-node")))
    elif isinstance(raw, str) and raw:
        if not _NODE_ID_RE.match(raw):
            raise ValueError(
                f"mqtt.homeassistant.discovery_node_id {raw!r}: use only letters, digits, '_' and '-'"
            )
        node_id = raw
    else:
        raise ValueError("mqtt.homeassistant.discovery_node_id must be true, false, or a string")
    return DiscoveryLayout(prefix=prefix, node_id=node_id, clear_legacy=clear)
