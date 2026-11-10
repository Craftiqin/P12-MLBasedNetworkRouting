# Step 3: physical ESP32 routing integration

## Model contract

The firmware embeds the Decision Tree code from the existing 2,781-byte
`simulation/inet/ml-routing/ml/generated/runtime-v2/DecisionTreeModel.h`.
The model code and `RouteFeatures` layout are checked against that export in
`tests/test_esp32_routing_contract.py`. All eight model inputs are `double`,
in this exact order:

| Index | Feature | Unit/type | Firmware source |
|---:|---|---|---|
| 0 | `upper_available` | Boolean as 0/1 | Fresh probe response from ESP32_02 plus its fresh Gateway path status |
| 1 | `upper_pdr_estimate` | Ratio 0–1 | Source probe response fraction × ESP32_02 measured Gateway probe success fraction |
| 2 | `upper_latency_ms` | Milliseconds | Half of measured source/relay probe RTT plus relay/Gateway probe RTT |
| 3 | `upper_hops` | Hop count | Path status hop count, measured by the probe/ACK exchange |
| 4 | `lower_available` | Boolean as 0/1 | Fresh probe response from ESP32_03 plus its fresh Gateway path status |
| 5 | `lower_pdr_estimate` | Ratio 0–1 | Source probe response fraction × ESP32_03 measured Gateway probe success fraction |
| 6 | `lower_latency_ms` | Milliseconds | Half of measured source/relay probe RTT plus relay/Gateway probe RTT |
| 7 | `lower_hops` | Hop count | Path status hop count, measured by the probe/ACK exchange |

ESP32_01 calls model only after both routes have at least five current probe
samples, fresh Gateway status, valid PDR and latency, and observed hop count.
If any input is unavailable/stale, source reports `ML INPUTS UNAVAILABLE` and
uses baseline route with ACK/retry. It does not substitute simulated values.
Valid model classes map directly: `0` -> ESP32_02; `1` -> ESP32_03; `-1` -> no
route. No hysteresis or post-model selector changes model's chosen next hop.

Current topology measures two hops (source, relay, Gateway). Step 2 training
data used synthetic three-hop inputs. Firmware passes actual two-hop counts;
this is a known model-domain mismatch. Hardware accuracy must be measured
before claiming the model performs well on device.

## Forwarding confirmation and telemetry

ESP32_02/03 probe their Gateway link and report measured latency, loss, RSSI,
availability, and hop count to ESP32_01. Their forwarding counters and ACK RTT
remain in serial link statistics. Gateway sends an internal delivery report
after accepting telemetry; selected relay forwards report to source. Source
displays `ML_ACTIVE` only after matching confirmation for current sequence,
relay, and model route. Timeout is shown as unconfirmed, never as success.

MeshPacket layout remains unchanged. Added packet type 7 is only a control
message. Existing P12 API schema is strict, so firmware sends no new JSON
fields. Existing `routingAlgorithm` codes: 1 baseline, 2 model class 0/upper,
3 model class 1/lower, 4 local no route. Firmware maps model class directly to
the selected route. Dashboard displays class implied by this field, selected
route, and persisted live-hardware forwarding result. API has no candidate
metrics or decision-history fields, so dashboard marks those unavailable.
Persisted `live_hardware` record confirms Gateway forwarding and API
persistence. Existing `latencyMs`, `packetLossPercent`, `throughputBps`,
`rssiDbm`, and `hopCount` carry measured route telemetry; throughput remains
null until measured across at least two Gateway-confirmed packets.

Firmware uses `experimentId=EXP-003` to identify direct prediction-to-route
semantics. P12 duplicate detection scopes sequence keys by experiment ID, so
older `EXP-001` rows remain intact and dashboard will not label them
`ML_ACTIVE`. Source sensor packets use a two-second cadence; Gateway API
publishing remains independently scheduled every five seconds. One-record-per-
interval API drain capacity is lower than sustained source rate, so bounded
queues can grow. Measure queue/drop counters; do not assume steady-state
buffering.

Gateway retains HTTPS/TLS, verified root CA, auth, existing API contract, and
five-second publication interval. No P11 Smart Crop route/schema/database
changes.

## Validation boundary

No physical ESP32 inputs were measured in this workspace. Firmware now
collects real inputs and only reports active routing after on-device
Gateway-confirmation events, but this run cannot claim ML routing is active.
Host C++ syntax checks do not equal ESP32 Arduino board builds. Step 2 tree was
trained on synthetic controlled scenarios, not hardware measurements.
