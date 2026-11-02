# ESP32 integration plan

## Final intended four-node design

Use four ESP32 DevKit V1 boards with 38-pin headers. Node 1 is the source, Nodes 2 and 3 are relay alternatives, and Node 4 is the destination. Planned paths: Node 1 → Node 2 → Node 4 and Node 1 → Node 3 → Node 4. ESP-NOW is a direct peer transport; multi-hop packet forwarding is application logic. Firmware and physical assembly are not implemented or verified.

Node 1 alone has one DHT11, one LDR, one sound sensor, and one 1.3-inch 128×64 I²C OLED. All four nodes have one traffic-light indicator module. Confirm exact module models, voltage, output type, current, level compatibility, driver needs, and pin mapping before wiring; no GPIO assignments are established. Node 4 is intended to export records to the FastAPI backend shown in the original project diagram; backend code/configuration is absent, so transport, schema, and successful delivery remain unverified.

## Proposed battery and regulated power path

Design: four 18650 lithium-ion cells, 3.7 V nominal and 2000 mAh each, in a 4S string; two dual-cell holders are intended as the mechanical arrangement. Nominal pack voltage is 14.8 V, full-charge voltage 16.8 V (4.2 V/cell), series capacity 2000 mAh, and nominal energy 29.6 Wh. These are arithmetic values, not measured pack performance. Verify cell matching, holder terminals, series connection, polarity, BMS wiring, connector/wire ratings, and insulation against the exact component documents.

Proposed distribution: cells → 4S balancing/protection BMS → main switch → four LM2596 converter inputs in parallel. Current design omits a fuse; this removes an overcurrent-protection layer. Adjust and measure each converter separately to 5.0 V for one ESP32. Do not parallel converter outputs or connect the 4S pack directly to a board. Verify cell matching, holder balance taps, wire gauge, connector limits, BMS protection/current ratings, and switch DC rating before energizing. The LM2596 IC data-sheet ratings do not establish a generic module's continuous output under project thermal conditions.

Use a charger compatible with a 4S lithium-ion pack and 16.8 V CC/CV termination. A BMS does not charge the cells. The candidate BMS listing advertises balancing and 40 A, while its charging specification says 16.8–18.1 V; resolve this ambiguity with the exact manufacturer/seller data before purchase or charging. Before connecting boards, test the protection path and polarity, set every rail with a meter, test each rail under load for stability/heat, and check USB/external-power interaction. Keep a bench supply as a separate, documented bring-up source until the battery path passes inspection.

## Packet, forwarding, and measurement plan

Frame fields: protocol version, source ID, destination ID, sequence/packet ID, source timestamp, hop count, hop limit, payload length, payload, and bounded path/visited-node history. Validate lengths, version, destination, path, duplicate cache, and hop budget before forwarding. Keep radio callbacks short and defer route processing to a worker.

Maintain neighbor state from discovery and probes. RSSI may be available in receive metadata depending on board/API. Probe/ACK round-trip gives RTT, not one-way latency without synchronized clocks. Estimate loss from counted sends/ACKs over a declared window; calculate throughput from delivered acknowledged bytes over a defined duration.

Keep minimum-hop baseline fixed and compare it with ML under identical workloads. The present model is Python-only, trained on synthetic observations, and has zero failure-class recall in the stored held-out evaluation. Do not port until real labeled observations, class-sensitive evaluation, Python/embedded parity tests, memory/time checks, and safe fallback pass.

Gateway logs packet IDs, receive time, route/path, sensor payload, route reason, and trial metadata. Preserve raw measurements, units, timestamps, model version, board identity, radio settings, and missing-value flags. Current/energy requires current instrumentation; do not infer it from packet counts.

## Physical validation sequence

1. Verify battery-holder topology, cell matching, balance taps, BMS documentation, compatible 16.8 V CC/CV charger, switch rating, and wiring with boards disconnected.
2. Measure all four 5.0 V rails under representative load; check heat, startup, stability, and USB/external-power isolation.
3. Bring up boards individually, then confirm direct peer send/receive and destination accounting.
4. Add packet framing, IDs, duplicate suppression, bounded hop count, loop rejection, and logs.
5. Implement fixed paths through each relay, then compare baseline and ML decisions on repeated matched trials.
6. Disable/degrade one corridor and measure route change, delivery, delay, and recovery. Record raw logs and preserve configuration.
7. Measure energy only with suitable instrumentation and a defined interval.

All physical steps remain planned until evidence is recorded.
