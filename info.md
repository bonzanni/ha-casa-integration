# Casa

Casa is the Home Assistant companion integration for the Casa app. It connects one **Casa** parent to the server's authenticated voice-agent
catalog and creates separate role-stable conversation entities for Butler,
Concierge, and future agents.
Each child keeps a fixed catalog role and its own client, connection,
availability, session, background route, and cleanup lifecycle; a missing or
failing role never falls back to another child.

**Requires:** Home Assistant 2026.4+ and Casa v0.125.0 or newer.

This integration needs Casa v0.125.0 or newer, so update Casa first if it is
older. Specialist handoff uses WebSocket protocol 3 and requires the complete
`background_jobs`, `endpoint_delivery`, and `voice_handoff` capability set. An
older protocol or a missing `voice_handoff` capability fails closed before a job
is created; there is no legacy handoff fallback.

A Casa server without `GET /api/voice/agents` cannot create a new entry or
reconcile its catalog. While that endpoint is unavailable, an existing entry with
retained children may load in degraded mode without catalog reconciliation, but
it cannot discover new, renamed, or restored agents.

When Casa runs as a Supervisor app, Home Assistant discovers it automatically. Confirm the displayed host and port to
connect; the versioned discovery record supplies the authenticated webhook
secret. If discovery is unavailable, use **Settings → Devices & services → Add
integration → Casa** and enter the exact host, port, and webhook secret
manually. Rediscovery of the same Supervisor UUID updates the stored endpoint
and secret, reloads the parent, and retains its Butler, Concierge, and future
voice-agent children.

Home Assistant names the parent **Casa**, each role device **Casa &lt;Role&gt;**,
and its conversation entity **Voice**. Thus Assist shows **Casa Butler → Voice**
and **Casa Concierge → Voice**. Configurable Casa persona names such as Tina or
Gary are descriptive metadata only; they never become pipeline-service identity.

The parent Configure action contains only satellite entity overrides. Reconfigure
each agent child to change session mode, WebSocket/SSE transport, or Assist idle
stability; role and name remain catalog-owned. Removing a still-advertised child
causes it to be recreated on the next reload with the same parent-plus-role
identity. Manual duplicates are rejected only for the exact host/port pair, so
different aliases for one server remain a documented limitation.

Deferred specialist answers are delivered to the device that asked, by whatever
that device can actually receive. A device with an announce-capable Assist
satellite is answered aloud on it; a device with only a Companion `notify`
entity — a phone or tablet — is sent the answer as a notification. A device
with neither is not promised a deferred answer at all, so Casa says up front
that it cannot follow up instead of promising an answer that never arrives.

The choice is made once, when the question is asked, from the asking device's
own entities — never from the shared WebSocket, which says nothing about any
one device. The spoken acknowledgement matches it: "I'll read it out when it
lands" only where the answer can be read out. A device with two announce-capable
satellites and no configured override is treated as having no audio endpoint,
because delivery would refuse it as ambiguous.

Delivery re-resolves the endpoint when the answer is ready and stays within the
promised modality, so a satellite that appears in the meantime never captures
an answer promised as a notification.

WebSocket background delivery is enabled only after Casa acknowledges protocol
3 and the complete `background_jobs`, `endpoint_delivery`, and `voice_handoff`
capability set for that exact agent route. Concierge handoff fails closed before
job creation for an older protocol or an incomplete registration; there is no legacy
handoff fallback. Its terminal `HandoffFrame` supplies the ordinary Assist
acknowledgement, after which the user may continue or cancel normally; the
completed result is announced when the originating satellite is idle. Butler
home-control turns remain direct. After successful audio, an ordinary WebSocket
reconnect keeps the manager's bounded process-local cache and suppresses a
replay. If its delivered acknowledgement was lost, a repeated summary remains
possible after a manager or integration process restart or delivered-cache
eviction; at-least-once delivery prefers that bounded duplicate risk over a
silently lost result.

Casa checks an HMAC of the empty HTTP upgrade body to authenticate the
integration client when the WebSocket is established. That handshake does not
authenticate individual frames, and plain `ws://` provides no encryption or
cryptographic server authentication. Keep the connection on a trusted
LAN/private network or carry it through an encrypted tunnel.
