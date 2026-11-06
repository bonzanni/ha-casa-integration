"""Contract tests for security and delivery guarantees in release docs."""

import json
import re
from pathlib import Path

import pytest


_ROOT = Path(__file__).parents[1]


def _normalized(filename: str) -> str:
    return " ".join((_ROOT / filename).read_text(encoding="utf-8").split())


@pytest.mark.parametrize("filename", ["README.md", "info.md"])
def test_websocket_security_boundary_is_explicit(filename):
    text = _normalized(filename)

    assert "HMAC of the empty HTTP upgrade body" in text
    assert "does not authenticate individual frames" in text
    assert "no encryption or cryptographic server authentication" in text


@pytest.mark.parametrize("filename", ["README.md", "info.md"])
def test_ack_loss_replay_boundary_is_explicit(filename):
    text = _normalized(filename)

    assert re.search(
        r"ordinary WebSocket reconnect.{0,240}"
        r"(?:without repeating|suppresses? (?:a )?replay)",
        text,
        re.IGNORECASE,
    )
    assert re.search(
        r"(?:summary may repeat|repeated summary remains possible).{0,260}"
        r"manager or integration process restart.{0,180}delivered-cache eviction",
        text,
        re.IGNORECASE,
    )
    assert re.search(
        r"(?:at least once|at-least-once).{0,320}"
        r"(?:silently lost|silent loss)",
        text,
        re.IGNORECASE,
    )

    assert "ordinary WebSocket reconnect replays" not in text
    assert "can never replay after a manager or integration process restart" not in text


def test_release_metadata_is_v090_with_existing_ha_minimum():
    manifest = json.loads(
        (_ROOT / "custom_components/casa/manifest.json").read_text(
            encoding="utf-8",
        ),
    )
    hacs = json.loads((_ROOT / "hacs.json").read_text(encoding="utf-8"))

    assert manifest["version"] == "0.9.0"
    assert hacs["homeassistant"] == "2026.4.0"


def test_readme_documents_catalog_parent_and_agent_children():
    text = _normalized("README.md")

    assert "one Casa parent" in text
    assert "separate role-stable conversation entities for Butler, Concierge" in text
    assert "There is no agent role field" in text
    assert "matching discovered role" in text
    assert "Casa Butler → Voice" in text
    assert "Casa Concierge → Voice" in text
    assert "stable role identity" in text
    assert "mutable catalog persona aliases" in text


def test_readme_documents_parent_and_child_configuration_boundaries():
    text = _normalized("README.md")

    assert "Parent configuration" in text
    assert "Satellite entity overrides" in text
    assert "Per-agent reconfiguration" in text
    assert "Session mode" in text
    assert "Transport" in text
    assert "Assist idle stability" in text
    assert "recreated on the next reload" in text
    assert "exact host and port" in text
    assert "different aliases for the same host" in text


@pytest.mark.parametrize("filename", ["README.md", "info.md"])
def test_coordinated_voice_handoff_upgrade_is_explicit(filename):
    text = _normalized(filename)

    assert "needs Casa v0.125.0 or newer" in text
    assert "WebSocket protocol 3" in text
    assert "background_jobs" in text
    assert "endpoint_delivery" in text
    assert "voice_handoff" in text
    assert "fails closed before a job is created" in text
    assert "no legacy handoff fallback" in text
    assert "GET /api/voice/agents" in text
    assert "cannot create a new entry" in text
    assert "existing entry with retained children may load in degraded mode" in text
    assert "without catalog reconciliation" in text


@pytest.mark.parametrize("filename", ["README.md", "info.md"])
def test_handoff_user_experience_and_butler_boundary_are_explicit(filename):
    text = _normalized(filename)

    assert "HandoffFrame" in text
    assert "continue or cancel normally" in text
    assert "originating satellite is idle" in text
    assert "Butler" in text
    assert "direct" in text


def test_readme_e2e_matrix_covers_dynamic_agent_release_boundaries():
    text = _normalized("README.md")

    assert "Real-system E2E" in text
    assert "Controlled fault-injection acceptance" in text
    assert "authenticated catalog" in text
    assert "Casa Butler → Voice" in text
    assert "Casa Concierge → Voice" in text
    assert "server utterance-to-first-text-block p95 below 1.5 seconds" in text
    assert "end-of-speech-to-first-audible-output p95 below 3.0 seconds" in text
    assert "Concierge background result" in text
    assert "missing role remains unavailable" in text
    assert "isolated cleanup" in text
    assert "catalog fixture" in text
    assert "WebSocket protocol proxy" in text
    assert "Home Assistant task and socket introspection" in text
    assert "non-listening state into `LISTENING`" in text
    assert "repeated `LISTENING` state update" in text
    assert "must not send another registration" in text
    assert "connected WebSocket child registers" in text
    assert "SSE" in text
    assert "`cancel` frame" in text
    assert "sibling remains usable" in text
    assert "without duplicate reauth prompts" in text
    assert "without replay" in text
    assert "must never be silently lost" in text
    assert "listening device once" not in text
    assert "present WebSocket child registers" not in text


@pytest.mark.parametrize("filename", ["README.md", "info.md"])
def test_deferred_delivery_endpoint_rules_are_explicit(filename):
    """The promise Casa makes is user-visible and must be documented.

    Each assertion is a commitment an operator can hold us to: which device
    answers, what happens when it cannot speak, and what happens when it can do
    neither. Silently promising an answer that never arrives is the failure
    these rules exist to end.
    """
    text = _normalized(filename)

    assert "delivered to the device that asked" in text
    assert "announce-capable Assist satellite" in text
    assert "notify" in text
    assert "is not promised a deferred answer at all" in text
    assert "two announce-capable satellites" in text
    assert "re-resolves the endpoint" in text


@pytest.mark.parametrize("filename", ["README.md", "info.md"])
def test_no_stale_protocol_numbers_survive_in_the_docs(filename):
    """Positive assertions alone let contradictions through.

    Both docs previously asserted "WebSocket protocol 3" in one paragraph while
    still calling the same thing a "protocol-2 route" two sections down. During
    a coordinated upgrade that ambiguity is what an operator acts on, so the
    obsolete phrasings are named and forbidden.

    Two protocol numbers are live at once and are NOT the same counter:
    route registration is 3; background delivery and the hand-off receipt are 2.
    """
    text = _normalized(filename)

    assert "protocol-2 route" not in text
    assert "protocol-2 voice-handoff" not in text
    assert "Protocol 1 or" not in text
    assert "protocol-1 routes" not in text
    assert "v0.7.0" not in text
    assert "v0.8.0" not in text
    assert "satellite_announce" not in text
