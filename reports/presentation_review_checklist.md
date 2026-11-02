# Presentation Review Checklist

## Current presentation status

- The existing presentation source still describes a generic 4–6 ESP32 arrangement and predates the final four-node hardware design in the report. Update its hardware/topology/power slides before using it for a review; do not treat it as the current hardware specification.
- Existing Python output values are synthetic software results. Verify source revision and reproduce with a run manifest before presenting them as reproducible results.
- OMNeT++/INET configuration exists, but build, run, forwarding, and result generation remain unverified. No custom ML module is configured there.
- Stored Decision Tree evaluation uses synthetic observations and has zero failure-class recall on its held-out strong-condition split.

## Final report hardware facts to carry into a future deck revision

- Four ESP32 DevKit V1 38-pin boards. Node 1 is source and sole sensing node; Nodes 2/3 are relays; Node 4 is destination.
- Node 1: DHT11, LDR, sound sensor, 1.3-inch 128×64 I²C OLED. Each node: one traffic-light indicator module.
- Paths: Node 1 → Node 2 → Node 4 and Node 1 → Node 3 → Node 4.
- Proposed 4S 18650 supply with BMS, switch (no fuse in current design), and four independent LM2596 5.0 V rails. Electrical specs and assembly remain unverified; show the commissioning gates and do not call the pack tested.

## Remaining presentation evidence

- Real prototype and measurement/logger photographs after implementation.
- Physical packet, route, delay, throughput, failure/recovery, and energy measurements.
- Model provenance reconciliation and held-out real failure-class evaluation.
- INET native output and trace verification if that stage remains in scope.
