"""Endpoint delivery capability — the promise Casa is allowed to make.

Casa may only promise a deferred answer the ASKING device can actually
receive. Every case here is a promise-then-silence failure we have either hit
in production or had flagged in review:

* an iPhone with no satellite was promised a spoken answer that expired unheard;
* a *fresh* phone's `notify` entity is legitimately `unknown` — rejecting that
  state would silently make new phones undeliverable;
* a device with two satellites would be promised audio and then nacked
  `satellite_ambiguous` at delivery time;
* a satellite appearing AFTER a `text` offer must not capture a delivery
  already promised as a notification.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.casa.capability import resolve_endpoint


def _entry(domain, entity_id):
    entry = MagicMock()
    entry.domain = domain
    entry.entity_id = entity_id
    return entry


def _state(state, features=0):
    st = MagicMock()
    st.state = state
    st.attributes = {"supported_features": features}
    return st


def _wire(monkeypatch, entries, states):
    monkeypatch.setattr(
        "custom_components.casa.capability.er.async_get", lambda hass: MagicMock())
    monkeypatch.setattr(
        "custom_components.casa.capability.er.async_entries_for_device",
        lambda reg, device_id, include_disabled_entities: entries)
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: states.get(eid)
    return hass


class TestAudioEndpoint:
    def test_announce_capable_satellite_offers_audio(self, monkeypatch):
        entries = [_entry("assist_satellite", "assist_satellite.kitchen")]
        hass = _wire(monkeypatch, entries,
                     {"assist_satellite.kitchen": _state("idle", 3)})
        offer = resolve_endpoint(hass, "dev-1")
        assert offer["modality"] == "audio"
        assert offer["receipt"] == "playback_complete"
        assert offer["entity_id"] == "assist_satellite.kitchen"

    def test_unavailable_satellite_is_not_offered(self, monkeypatch):
        entries = [_entry("assist_satellite", "assist_satellite.kitchen")]
        hass = _wire(monkeypatch, entries,
                     {"assist_satellite.kitchen": _state("unavailable", 3)})
        assert resolve_endpoint(hass, "dev-1") is None

    def test_satellite_without_announce_is_not_offered(self, monkeypatch):
        """features=2 is START_CONVERSATION only — it cannot announce."""
        entries = [_entry("assist_satellite", "assist_satellite.kitchen")]
        hass = _wire(monkeypatch, entries,
                     {"assist_satellite.kitchen": _state("idle", 2)})
        assert resolve_endpoint(hass, "dev-1") is None

    def test_two_satellites_without_override_are_not_offered(self, monkeypatch):
        """Delivery would nack this as ambiguous — never promise it."""
        entries = [_entry("assist_satellite", "assist_satellite.a"),
                   _entry("assist_satellite", "assist_satellite.b")]
        hass = _wire(monkeypatch, entries,
                     {"assist_satellite.a": _state("idle", 3),
                      "assist_satellite.b": _state("idle", 3)})
        assert resolve_endpoint(hass, "dev-1") is None

    def test_override_disambiguates(self, monkeypatch):
        entries = [_entry("assist_satellite", "assist_satellite.a"),
                   _entry("assist_satellite", "assist_satellite.b")]
        hass = _wire(monkeypatch, entries,
                     {"assist_satellite.a": _state("idle", 3),
                      "assist_satellite.b": _state("idle", 3)})
        offer = resolve_endpoint(
            hass, "dev-1", overrides={"dev-1": "assist_satellite.b"})
        assert offer["entity_id"] == "assist_satellite.b"


class TestTextEndpoint:
    def test_fresh_phone_notify_entity_offers_text(self, monkeypatch):
        """A notify entity's state is the last-notification timestamp, so a
        phone that has never been notified is `unknown` — and usable."""
        entries = [_entry("notify", "notify.mobile_app_phone")]
        hass = _wire(monkeypatch, entries,
                     {"notify.mobile_app_phone": _state("unknown")})
        offer = resolve_endpoint(hass, "dev-2")
        assert offer["modality"] == "text"
        assert offer["receipt"] == "accepted"

    def test_unavailable_notify_is_not_offered(self, monkeypatch):
        entries = [_entry("notify", "notify.mobile_app_phone")]
        hass = _wire(monkeypatch, entries,
                     {"notify.mobile_app_phone": _state("unavailable")})
        assert resolve_endpoint(hass, "dev-2") is None

    def test_phone_without_any_endpoint_offers_nothing(self, monkeypatch):
        """The live failure: an iPhone with trackers and sensors only."""
        entries = [_entry("device_tracker", "device_tracker.phone"),
                   _entry("sensor", "sensor.phone_battery")]
        hass = _wire(monkeypatch, entries, {})
        assert resolve_endpoint(hass, "dev-2") is None


class TestModalityScoping:
    def test_audio_is_preferred_when_both_exist(self, monkeypatch):
        entries = [_entry("notify", "notify.mobile_app_x"),
                   _entry("assist_satellite", "assist_satellite.kitchen")]
        hass = _wire(monkeypatch, entries,
                     {"assist_satellite.kitchen": _state("idle", 3),
                      "notify.mobile_app_x": _state("unknown")})
        assert resolve_endpoint(hass, "dev-3")["modality"] == "audio"

    def test_text_request_never_returns_the_satellite(self, monkeypatch):
        """Delivery-time scoping: a satellite that appeared after a `text`
        offer must not capture a delivery promised as a notification."""
        entries = [_entry("notify", "notify.mobile_app_x"),
                   _entry("assist_satellite", "assist_satellite.kitchen")]
        hass = _wire(monkeypatch, entries,
                     {"assist_satellite.kitchen": _state("idle", 3),
                      "notify.mobile_app_x": _state("unknown")})
        offer = resolve_endpoint(hass, "dev-3", modality="text")
        assert offer["modality"] == "text"
        assert offer["entity_id"] == "notify.mobile_app_x"

    def test_audio_request_does_not_fall_back_to_text(self, monkeypatch):
        entries = [_entry("notify", "notify.mobile_app_x")]
        hass = _wire(monkeypatch, entries,
                     {"notify.mobile_app_x": _state("unknown")})
        assert resolve_endpoint(hass, "dev-3", modality="audio") is None


class TestRobustness:
    def test_registry_failure_returns_none_not_raise(self, monkeypatch):
        def boom(hass):
            raise RuntimeError("registry down")
        monkeypatch.setattr(
            "custom_components.casa.capability.er.async_get", boom)
        assert resolve_endpoint(MagicMock(), "dev-9") is None

    def test_non_integer_supported_features_is_skipped(self, monkeypatch):
        entries = [_entry("assist_satellite", "assist_satellite.kitchen")]
        st = _state("idle")
        st.attributes = {"supported_features": "three"}
        hass = _wire(monkeypatch, entries, {"assist_satellite.kitchen": st})
        assert resolve_endpoint(hass, "dev-9") is None
