# P12-IOT Step 4 — autonomous routing controller specification

> **Supersedes** the earlier read-only dashboard scope below. This is the
> required operating design. It is not evidence that the controller is deployed
> or that physical autonomous routing works.

## Intended operating mode and ownership

Autonomous ML control is normal operating mode when explicitly enabled in the
Streamlit control. No operator approval gates an eligible route change. The
toggle starts disabled after process restart unless a durable desired-state
setting is added; the dashboard must show `ENABLED`, `DISABLED`, or
`UNAVAILABLE` from confirmed control-plane state, not merely its local toggle.

Route ownership is exclusive per mesh epoch:

| State | Route authority | ESP32_01 behavior |
|---|---|---|
| ML control enabled and lease fresh | Python policy via authenticated Worker command | Apply only valid ML commands; suppress embedded model route changes |
| ML control disabled, lease expired, controller/API unavailable | Embedded Decision Tree and existing safe selector | Ignore ML commands; continue normal mesh forwarding |
| Transition | ESP32_01 keeps current valid route until ownership transition is acknowledged | Do not let both selectors write route state |

Worker stores desired control state and monotonically increasing control epoch.
ESP32_04 polls state/commands. A disable transition increments epoch, stops
new command issuance, and sends a revocation/ownership message; it does not
clear the active route or interrupt forwarding. ESP32_01 accepts commands only
for current epoch while ML ownership is active. Lease expiry returns ownership
to firmware fallback. On boot, firmware owns routing until it receives a fresh
enabled epoch and acknowledges it.

## Autonomous workflow

1. Streamlit refreshes `/p12/iot-data` and `/p12/routing-events` continuously
   (bounded polling interval, request timeout, incremental history). It also
   reads current control state and pending command/ack state from the Worker.
2. Python validates provenance, sequence/uptime monotonicity, required feature
   completeness, clock age, candidate reachability, and model-domain bounds.
   Stale, incomplete, invalid, or unreliable observations produce a logged
   `HOLD` decision and never a command.
3. The existing trained model and route-selection policy score reachable
   candidates only. Confidence is the model probability for selected candidate
   class. A command is eligible only if confidence and measured link-quality
   improvement exceed calibrated thresholds, candidate telemetry is fresh, and
   selected route differs from the confirmed active route.
4. Hysteresis requires the same candidate to remain eligible across a
   configurable number of fresh observations. A configurable minimum interval
   between changes prevents oscillation. Defaults must come from held-out
   existing data plus measured hardware calibration; do not invent numeric
   defaults. Until calibration exists, autonomous command issuance remains
   unavailable and the embedded Decision Tree owns routing.
5. Streamlit sends an authenticated, idempotent command to the Worker. Command
   includes command ID, control epoch, source/destination, requested next hop,
   creation/expiry times, evidence sequence, expected current route, and policy
   version. Worker rejects expired, replayed, stale-epoch, duplicate-conflict,
   or malformed commands. Retries are bounded and reuse same command ID.
6. ESP32_04 retrieves pending commands over existing verified HTTPS/TLS,
   validates envelope/expiry/epoch, then relays the command to ESP32_01 with
   ESP-NOW. ESP32_01 validates destination, epoch, expiry, command ID/replay
   cache, reachable fresh neighbor, loop-free route, and expected current route.
   It atomically updates the actual packet-forwarding next hop only after all
   checks pass. Repeated same command returns prior result; already-active
   target is acknowledged as `NO_CHANGE`.
7. ESP32_01 ACKs command ID and applied route over ESP-NOW. ESP32_04 reports
   execution result to authenticated Worker endpoint. Streamlit correlates
   command, ACK, route-change event, and subsequent delivery/performance window.
   It records `IMPROVED`, `NOT_IMPROVED`, or `INSUFFICIENT_EVIDENCE`; it never
   equates command acceptance with successful forwarding.
8. Log every input snapshot reference, prediction/probability, candidate score,
   hold/issue decision and reason, command/retry, Worker response, device ACK,
   actual route change, ownership transition, fallback, and verification result.

## Required Worker and device API additions

These are additive P12-only routes. Keep existing P11 routes, schemas, and
tables untouched. Require separate P12 bearer authentication and strict
schemas. Additive persistent storage needs migrations and uniqueness on command
ID, plus append-only decision/execution events.

- `GET /p12/routing-control` — current enabled state and epoch.
- `PUT /p12/routing-control` — authenticated desired state; idempotent epoch
  transition.
- `POST /p12/routing-commands` — enqueue validated command; duplicate ID with
  same body returns original result, conflicting body rejects.
- `GET /p12/routing-commands/pending?nodeId=4` — bounded pending commands.
- `POST /p12/routing-commands/{commandId}/result` — gateway execution/ACK
  result, deduplicated by command ID and result sequence.
- `GET /p12/routing-commands/{commandId}` — command lifecycle and correlated
  device result for dashboard.

Firmware protocol must add a dedicated bounded command frame; do not overload
sensor telemetry or dynamic channel-sync markers. Keep callbacks enqueue-only,
and do HTTPS/JSON outside ESP-NOW callbacks. Preserve current channel sync,
sensors, OLED, LEDs, verified TLS, telemetry queues, and firmware fallback.
Replay cache and retry queue must be bounded and expose overflow/failure logs.

## Threshold calibration and safety gates

Use grouped held-out model runs for initial probability calibration; report
precision/recall and false route-switch rate by condition. Then calibrate link
improvement against paired hardware observation windows with identical traffic
loads. Persist calibration version and data range with each decision. Threshold
config must be bounded and validated. Missing calibration, poor calibration,
unknown candidate reachability, clock-unsynced command expiry, stale telemetry,
or unavailable API all fail closed to firmware ownership. Firmware Decision
Tree remains available when Python or internet is down.

## Physical acceptance criterion

Do not claim physical autonomous routing operational until hardware logs show a
real telemetry snapshot -> Python prediction/policy decision -> authenticated
Worker enqueue -> ESP32_04 retrieval -> ESP-NOW delivery -> ESP32_01 validation
and forwarding-table application -> ESP32_01 ACK -> ESP32_04 result report ->
subsequent measured performance verification. Source-level tests, simulations,
fake APIs, or dashboard display do not satisfy this criterion.

## Implementation state

The repository currently has read-only Streamlit telemetry and routing-event
history, plus embedded Decision Tree routing. The existing Worker source has
sensor and routing-event endpoints only; no control-state, command queue, or
result endpoints. Current dashboard does not execute Python decisions or
submit commands. Thus the workflow above is the implementation specification,
not completed software. Complete implementation requires additive Worker
changes in the P11 checkout, coordinated firmware protocol changes across all
four boards, end-to-end tests, and physical hardware validation. No manual
approval is part of the target workflow.

---

## Prior read-only telemetry contract and evidence

## Contract and isolation

The existing P12 sensor contract remains `POST/GET /p12/iot-data` with its original strict field set. A new P12-only contract adds:

- `POST /p12/routing-events` — Bearer-authenticated event ingestion.
- `GET /p12/routing-events?limit=50` — read-only event history for Streamlit.
- Read envelope: `{ "events": [...], "totalGatewayReceived": 1 }`.
- New PostgreSQL table: `p12_iot_routing_events`, with a P12-scoped uniqueness key over project, network, source, experiment, sequence, and source uptime.

P11 `/sensor-data`, its schema, database table, auth, and business logic are not modified. The route is intended for the existing `smart-crop-api` Worker on `api.craftiq.in`; no Worker route or DNS change is needed. The SQL migration is additive and is not applied by this code change.

## Routing-event JSON example

```json
{
  "projectId": "P12-IOT",
  "networkId": "P12-MESH-01",
  "experimentId": "EXP-003",
  "sourceNodeId": 1,
  "currentNodeId": 1,
  "selectedNextHopId": 2,
  "forwardingNodeId": 2,
  "sequence": 74,
  "sourceUptimeMs": 47000,
  "routingMode": "ML_ACTIVE",
  "featureValid": true,
  "predictedClass": 0,
  "candidateUpper": {"available": true, "pdr": 0.9, "latencyMs": 12.0, "hops": 2.0},
  "candidateLower": {"available": false, "pdr": 0.7, "latencyMs": 28.0, "hops": 2.0},
  "modelFeatures": [1.0, 0.9, 12.0, 2.0, 0.0, 0.7, 28.0, 2.0],
  "forwardingResult": "GATEWAY_RECEIVED",
  "ackResult": "NOT_OBSERVED",
  "hopCount": 2,
  "routeChanged": true,
  "routeChangeReason": "model_class_upper",
  "sourcePacketsSent": 74
}
```

`ackResult=NOT_OBSERVED` is deliberate: the Gateway has received the data packet, but its asynchronous ESP-NOW ACK send has no confirmation callback. The event never claims that the source received that ACK. `GATEWAY_RECEIVED` confirms only the packet’s arrival at Gateway. A failed/no-route decision cannot be posted through this mesh when no route reaches Gateway, so API event history is delivery-biased; OLED/serial remain the local failure evidence.

## Firmware and dashboard

All four firmware files now share protocol version 2 and the same packed packet layout. ESP32_01 adds the original eight model features, validity, prediction, selected first hop, reason, route-change flag, and cumulative sent count. Relays preserve those fields. ESP32_04 keeps the existing five-second sensor publisher and TLS/root-CA/auth implementation, and has a separate 16-entry routing-event queue with retry, route-change preference, and explicit overflow/eviction counters. ESP-NOW callbacks still only enqueue receive frames; JSON and HTTPS execute in the main loop.

The Streamlit Live P12 tab reads only `/p12/iot-data` and `/p12/routing-events`. It separates current live hardware from stale historical records and the simulation tabs. It displays N/A for missing features, end-to-end latency (not collected by this packet contract), and failed transmissions (not observable from a Gateway-only event stream). PDR/loss are computed only for intervals between Gateway-confirmed events from measured source sent-counter deltas; the dashboard does not synthesize a failure count. Data older than 15 seconds is marked stale.

## Validation and deployment state

- P12 root tests: 19 passed, including routing contract, dashboard parsing/freshness/missing metrics/data separation, simulator tests, and embedded-model parity.
- Worker API tests against the applied source: 24 passed; PostgreSQL integration tests: 2 skipped because `WORKER_TEST_DATABASE_URL` is not configured. The local Python 3.11 test runner lacks `pg8000`, so the test process stubbed the driver import; API route tests use a fake database.
- Compiled the gateway routing JSON serializer with a host C++ stub and validated its emitted JSON against the Worker’s Pydantic ingestion model.
- `app.py` and dashboard helper modules pass `py_compile`.
- No live database persistence test, deployed authenticated POST, deployed GET, or P11 production regression request was run.
- The production PostgreSQL schema was not introspected; the connected Neon account returned no CraftIQ/P11 project. The new migration therefore remains unapplied.
- Worker source at `the separate P11 Worker checkout (outside this repository)` was updated with the additive patch; that directory has no Git metadata. Production has not been deployed, and no migration has been applied.
- Cloudflare account authentication is available through the connected Cloudflare API tool; the Wrangler CLI is not installed in this shell. The checked-in Wrangler config identifies `smart-crop-api` and its existing `api.craftiq.in` custom domain/Hyperdrive binding. No Worker route or DNS was changed.
- `arduino-cli` and PlatformIO are unavailable here. The files have static/contract coverage but no ESP32 Arduino board compile or physical hardware test.
- Protocol version 2 changes ESP-NOW packet size/layout; all four nodes must be reflashed together. Mixed version 1/version 2 nodes will reject each other’s frames.
- Firmware credentials remain build-time placeholders unless configured for the device. Never commit the device bearer token.

Physical ML forwarding remains unverified until all nodes are flashed, real probe windows satisfy the model gate, packets traverse the predicted relay, and Gateway/source confirmations are observed on hardware.
