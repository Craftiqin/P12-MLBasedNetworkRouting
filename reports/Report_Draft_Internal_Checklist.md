# Report Draft Review Notes

The final report is `IoT_Mesh_Intelligent_Routing_Report_70_Plus_Pages.docx`; its rendered and visually reviewed PDF is maintained beside it. This checklist tracks remaining submission evidence, not missing design intent.

## Confirm before submission

- Student name, register number, degree wording, department, institution, guide, chairperson, examiners, academic year, and address.
- Reproduce saved Python model and trial outputs with a versioned manifest; reconcile model seed 3 with documented/default seed 17 and identify which artifact produced the stored outputs.
- Build/run OMNeT++/INET and preserve native output files if that simulation stage remains in scope.
- Verify PEARL and all other bibliography entries against department citation requirements and primary bibliographic records.
- Confirm exact ESP32 board revisions, sensor/display/indicator part numbers, wiring/pin map, radio settings, BMS, switch DC rating, charger, and power module specifications before assembly.

## Hardware design now documented

- Four ESP32 DevKit V1 38-pin boards: Node 1 source/sensing; Nodes 2 and 3 relay alternatives; Node 4 destination.
- Node 1 only: one DHT11, one LDR, one sound sensor, and one 1.3-inch 128×64 I²C OLED. One traffic-light indicator module per node.
- Proposed paths: Node 1 → Node 2 → Node 4 and Node 1 → Node 3 → Node 4.
- Proposed power design: four 3.7 V, 2000 mAh 18650 cells in 4S; two dual-cell holders; 4S balancing/protection BMS; main switch; no fuse in current design; four separate LM2596 5.0 V rails, one per board; compatible 4S CC/CV charger.
- Cell holder wiring, BMS and charger compatibility, overcurrent-protection review, module load/thermal ratings, sensor and indicator interfaces, backend configuration, and all physical measurements remain unverified. No assembly or purchase is claimed.

## Evidence and photographs still needed

- Insert genuine prototype and measurement/logger photographs into the labelled Figure 5.1 and 5.2 placeholders after implementation.
- Record board identity, firmware, radio channel, placement, trial workload, packet IDs, route/path, RSSI/ACK/RTT, delivery, latency, throughput, recovery, and raw logs.
- Collect repeated matched baseline/ML trials and class-sensitive held-out failure evaluation using real link labels.
- Measure current/energy with suitable instrumentation and a defined interval; do not infer energy from packet counts.
- Verify electrical rails and protections with boards disconnected before connecting the pack; then validate each 5.0 V output under load and check USB/external-power interactions.
