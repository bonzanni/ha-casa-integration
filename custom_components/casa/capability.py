"""Which endpoint can receive a deferred answer for a given device.

Casa must decide BEFORE promising a deferred answer whether the ASKING device
can receive one, and by which modality — otherwise it promises a spoken answer
to a phone that can only show a notification, and the finished answer is
silently discarded (casa-ha-app #233/#224).

Route capabilities cannot answer that: they describe the WebSocket connection,
which every device on this Home Assistant shares. Capability belongs to the
ENDPOINT, so it is resolved here from Home Assistant's own registries.

ONE function serves both phases — the utterance-time offer and the
delivery-time dispatch. That is deliberate: if the two used different rules,
Casa could promise audio on a device whose satellite delivery later rejects as
ambiguous, or a satellite appearing after a `text` offer could capture a
delivery already promised as a notification. Both were identified in review as
promise-then-silence seams.

What crosses the wire to Casa is generic — `audio` or `text`, plus how strong
the receipt is. Casa never learns `assist_satellite`, `notify`, or entity ids.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

# AssistSatelliteEntityFeature.ANNOUNCE. Not imported from the assist_satellite
# component so this integration keeps loading if that component moves; the flag
# is part of HA's documented entity-feature contract and is exposed as the
# `supported_features` state attribute (verified live: a Home Assistant Voice
# satellite reports 3 = ANNOUNCE|START_CONVERSATION).
ANNOUNCE_FEATURE = 1

# State rules differ BY DOMAIN and must not be shared. A `notify` entity is
# stateless — its state is the last-notification timestamp — so a phone that has
# never been notified is legitimately `unknown` and is perfectly usable. A
# satellite in `unknown` is not known to be reachable, so it is not offered.
_SATELLITE_UNUSABLE = frozenset({"unavailable", "unknown"})
_NOTIFY_UNUSABLE = frozenset({"unavailable"})

AUDIO = "audio"
TEXT = "text"


def resolve_endpoint(
    hass: HomeAssistant,
    device_id: str,
    modality: str | None = None,
    overrides: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    """The endpoint that can take a deferred answer for ``device_id``.

    ``modality=None`` picks the best available (utterance time). Passing
    ``"audio"`` or ``"text"`` restricts the search to that modality, which is
    what delivery must use so a late-appearing satellite cannot capture a
    delivery already promised as text.

    Preference is by strength of the promise we can honestly make:

    1. an ``assist_satellite`` on this device supporting ANNOUNCE and reachable
       -> ``audio``. HA's contract is that announce returns only once playback
       finishes, so ``playback_complete`` is a real receipt.
    2. a ``notify`` entity on this device (the Companion app) -> ``text``, with
       receipt ``accepted``: push infrastructure confirms hand-off, never that
       a human saw it.

    ``None`` means: do not promise a deferred answer for this device.
    """
    try:
        registry = er.async_get(hass)
        entries = list(er.async_entries_for_device(
            registry, device_id, include_disabled_entities=False,
        ))
    except Exception:  # noqa: BLE001 - capability probing must never break a turn
        _LOGGER.exception("Casa: entity lookup failed for device %s", device_id)
        return None

    if modality in (None, AUDIO):
        found = _satellite_for(hass, entries, device_id, overrides or {})
        if found is not None:
            return {
                "modality": AUDIO,
                "receipt": "playback_complete",
                "entity_id": found,
            }

    if modality in (None, TEXT):
        for entry in entries:
            if entry.domain != "notify":
                continue
            state = hass.states.get(entry.entity_id)
            # A registry row can outlive its entity: the platform may be
            # unloaded, or the entity not yet added to the state machine. It
            # would then look deliverable here and fail at the service call,
            # after Casa has already been told the answer is going out.
            if state is None or state.state in _NOTIFY_UNUSABLE:
                continue
            return {
                "modality": TEXT,
                "receipt": "accepted",
                "entity_id": entry.entity_id,
            }

    _LOGGER.debug(
        "Casa: device %s has no %s endpoint",
        device_id, modality or "deferred-delivery",
    )
    return None


def _satellite_for(
    hass: HomeAssistant,
    entries: list[Any],
    device_id: str,
    overrides: Mapping[str, str],
) -> str | None:
    """One usable announce-capable satellite, applying the SAME ambiguity and
    override rules delivery uses (``SatelliteDirectory.resolve``).

    A device with two satellites and no override is NOT offered: delivery would
    reject it as ambiguous, and promising an answer we will then refuse to
    deliver is the exact failure mode this module exists to prevent.
    """
    usable = []
    for entry in entries:
        if entry.domain != "assist_satellite":
            continue
        state = hass.states.get(entry.entity_id)
        if state is None or state.state in _SATELLITE_UNUSABLE:
            continue
        try:
            features = int(state.attributes.get("supported_features") or 0)
        except (TypeError, ValueError):
            continue
        if features & ANNOUNCE_FEATURE:
            usable.append(entry.entity_id)

    if not usable:
        return None

    override = overrides.get(device_id)
    if override is not None:
        return override if override in usable else None

    if len(usable) != 1:
        _LOGGER.debug(
            "Casa: device %s has %d announce-capable satellites and no "
            "override — not offering audio", device_id, len(usable),
        )
        return None
    return usable[0]
