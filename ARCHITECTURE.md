# Architecture decisions

- **Runtime:** Python 3.11, NetworkX, NumPy/pandas, scikit-learn, Streamlit, Plotly. Dependencies are already installed locally; `requirements.txt` pins compatible minimums.
- **Simulation:** deterministic seeded graph, discrete packet forwarding, Bernoulli per-link delivery, simulation-time latency, optional congestion multiplier and explicit link state. RSSI/capacity are synthetic metrics, not ESP32 measurements.
- **Baseline:** deterministic shortest-hop path over links available at forwarding time; equal paths resolve lexicographically. No ML inputs.
- **ML:** Decision Tree predicts one-hop delivery ACK from current synthetic RSSI, latency, loss, throughput, and remaining hop distance. Training/evaluation split is by independent generated run IDs, with test conditions held apart. Candidate cost is `1 - P(success) + neighbor_remaining_cost`; path estimate composes per-link success probabilities along shortest-hop continuation. Switching margin prevents noisy route changes.
- **Experiments:** each algorithm sees same topology, scenario, and seed. Outputs include trial-level and aggregate CSVs; no energy claims.
- **UI:** Streamlit calls pure simulation/experiment APIs. No database, cloud, or hardware dependency.
- **Hardware boundary:** simulator packet and link interfaces are intended to map to ESP-NOW application forwarding, ACK/probe-derived metrics, duplicate cache, and hop limits. Synthetic results do not establish radio performance.

## Simplifications

Simulation processes packets sequentially. Link delay is sampled as configured latency with congestion adjustment; loss is per transmission. There is no radio interference model, collision scheduling, MAC retry model, battery model, mobility, or true one-way clock synchronization. Recovery is reported only when a post-failure successful delivery occurs; otherwise censored.


## Planned physical hardware design

The intended build has four ESP32 DevKit V1 38-pin nodes: Node 1 is the source, Nodes 2 and 3 are alternative relays, and Node 4 is the destination. Only Node 1 has one DHT11, one LDR, one sound sensor, and one 1.3-inch 128×64 I²C OLED. Each node has one traffic-light indicator. Intended paths are Node 1 → Node 2 → Node 4 and Node 1 → Node 3 → Node 4. This is a design plan; firmware, physical assembly, and radio tests remain unverified.

The proposed supply uses four 3.7 V, 2000 mAh 18650 cells in 4S configuration (14.8 V nominal, 16.8 V full, 2000 mAh series capacity, 29.6 Wh nominal), two dual-cell holders, a 4S balancing/protection BMS, main switch (no fuse in current design), and four LM2596 modules. Inputs are parallel from protected battery output; each converter is separately adjusted/measured to 5.0 V for one ESP32, and outputs are kept separate. Holder wiring and BMS cell taps/pinout/ratings, 16.8 V CC/CV charger, switch DC rating, module capability, sensor/indicator interfaces, and USB/external-power isolation must be verified before assembly. Candidate BMS listing's charge-voltage range is ambiguous. BMS is not a charger; a compatible 4S 16.8 V CC/CV charger is required. No fuse is included, removing an overcurrent-protection layer; verify the wiring, cell matching, BMS protection/current rating, and connector limits before energizing.
