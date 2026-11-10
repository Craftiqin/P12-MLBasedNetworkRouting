# P12-IOT Step 2 — ML validation and ESP32 preparation

**Scope:** validation and deployment preparation only. Four Step 1 firmware files were not changed. No model was connected to firmware, no live API data was relabeled, and no simulation output or historical dataset was overwritten.

## Existing implementations inspected

P12 contains two distinct trees:

1. `ml/models/delivery_tree.joblib` from `ml/pipeline.py` predicts whether one **synthetic link attempt** succeeds. Its target is `delivery_success` (ACK outcome), not a next-hop choice. `routing/engines.py` turns its estimated success probabilities into a route cost in the Python graph simulator.
2. `simulation/inet/ml-routing/ml/generated/runtime-v2/DecisionTreeModel.h` is the existing compact route-choice tree. Its matching trainer, dataset, JSON tree, metrics, policy fallback, tests, and paired AODV results are under `simulation/inet/ml-routing/`. This is the relevant current embedded candidate; it remains a separate INET simulator model and has not been installed in ESP32 firmware.

No physical-radio training rows exist. Root `ml/data/synthetic/link_observations.csv` and INET `ml/data/route_scenarios.csv` are generated synthetic data. OMNeT++/INET result artifacts are simulator output, not ESP32 measurements.

## Root delivery-tree audit

Re-trained in a temporary directory with default config (60 synthetic runs, seed 17) so checked-in files remained unchanged. Source uses seed 17 for both NumPy generation and `DecisionTreeClassifier.random_state`; current files show no model/data seed mismatch. The artifact's `run_id`-group split is disjoint, but the default ordering leaves only the `strong` condition in test. Its stored result reproduces:

| Metric | Result |
|---|---:|
| Accuracy | 0.9526 |
| Success precision / recall / F1 | 0.9618 / 0.9900 / 0.9757 |
| Failure precision / recall / F1 | 0.1333 / 0.0377 / 0.0588 |
| Confusion matrix, rows actual `[failure, success]`, columns predicted `[failure, success]` | `[[2, 51], [13, 1284]]` |

The earlier documentation claim of failure recall 0.0 was stale. Current value is **3.77%**. The model predicts safe/success for 51 of 53 synthetic failures in this holdout, so this model is unsuitable for failure-aware ESP32 routing despite 95.26% accuracy. No root model artifact was overwritten.

## Route-choice tree contract and evaluation

Existing INET model: `DecisionTreeClassifier(max_depth=4, min_samples_leaf=3, random_state=20261101)`, with no feature scaling. Generator uses seed 20261101. Dataset has 600 synthetic route scenarios: 480 rows from run IDs 0–79 for training; 120 rows from run IDs 80–99 for held-out testing. Runs are kept intact across partitions. The CSV column named `seed` contains run IDs; generator seed is recorded in model metadata and source. This naming is potentially confusing, but current generation/training seeds agree.

Feature order and C++ types: eight finite `double` values, in this exact order:

1. `upper_available` (0/1)
2. `upper_pdr_estimate` (0..1)
3. `upper_latency_ms` (>=0)
4. `upper_hops` (>=1)
5. `lower_available` (0/1)
6. `lower_pdr_estimate` (0..1)
7. `lower_latency_ms` (>=0)
8. `lower_hops` (>=1)

Upper/lower are the two configured candidate paths. Target `label_route`: `0` selects upper, `1` selects lower, `-1` means neither route usable. Labels are computed from the synthetic generator's expected completion cost `PDR * latency + (1-PDR) * 1000 ms`; ties choose upper. The generator explicitly marks unavailable routes and includes a no-route case. This is a defensible **synthetic objective**, not an observed outcome. Both hop counts are fixed at 3 in current data, so hop-count effects are not learned.

Held-out test results (labels `[-1, 0, 1]`; confusion matrix rows actual, columns predicted):

| Label | Meaning | Precision | Recall | F1 | Support |
|---:|---|---:|---:|---:|---:|
| -1 | no usable route | 1.000 | 1.000 | 1.000 | 5 |
| 0 | upper path | 0.926 | 0.926 | 0.926 | 27 |
| 1 | lower path | 0.977 | 0.977 | 0.977 | 88 |

Accuracy **0.9667**, macro precision/recall/F1 **0.9677**. Confusion matrix: `[[5,0,0],[0,25,2],[0,2,86]]`. No no-route case was predicted as a usable route (5/5); support is small.

Five-fold `GroupKFold`, grouping by run ID and using training partition only, produced accuracy **0.9458**, macro F1 **0.9450**, no-route recall **1.000** (20/20). Confusion matrix: `[[20,0,0],[0,88,11],[0,15,346]]`. CV and holdout both remain within same synthetic condition families; neither tests unseen physical environments.

Safe inference is provided by `ml/route_policy.py` and generated C++ `selectSafely`: reject unavailable/invalid candidates, use deterministic expected-cost fallback for invalid or unusable model output, return `-1` when neither candidate is valid. Labels are decisions, not calibrated confidence scores. No scaling or learned confidence is used.

## Embedded export

Existing standalone C++ export: [`DecisionTreeModel.h`](../../simulation/inet/ml-routing/ml/generated/runtime-v2/DecisionTreeModel.h). It has no Arduino or OMNeT++ dependency, uses 21 nodes / 11 leaves, and is **2,781 bytes** as source. Model arrays occupy about 504 bytes when represented as four 32-bit integer arrays plus one 64-bit threshold array; compiler/linker placement and final ESP32 flash/RAM size are not measured. Inference follows one tree path (depth at most 4) and checks 8 inputs for finiteness. No physical ESP32 latency benchmark was run.

The existing C++ parity test compiles the generated header with `clang++` and compares all held-out Python predictions. It also checks invalid-metric and safe-fallback behavior. That test passed in this workspace.

## Simulator baseline comparison

Existing paired INET results use five matched seeds (17–21), AODV baseline, and synthetic traffic. Values below are mean ± sample SD; they are simulation evidence only. Packet loss is `1 - PDR`.

| Scenario | AODV PDR | Tree PDR | AODV mean delay | Tree mean delay |
|---|---:|---:|---:|---:|
| Healthy | 0.9993 ± 0.0016 | 0.9600 ± 0.0894 | 5.21 ± 2.99 ms | 89.37 ± 194.82 ms |
| Degraded reliability | 0.2900 ± 0.1615 | 0.6929 ± 0.0621 | 4293.5 ± 2657.3 ms | 4798.2 ± 547.8 ms |
| Increased latency | 0.9986 ± 0.0032 | 0.9671 ± 0.0442 | 22.82 ± 7.43 ms | 283.21 ± 410.08 ms |
| Relay failure | 0.9986 ± 0.0020 | 0.9800 ± 0.0447 | 5.55 ± 2.90 ms | 240.91 ± 251.05 ms |

Tree improves delivery only in the degraded-reliability scenario in this table; it performs worse on healthy, high-latency, and relay-failure rows. Existing relay-failure “recovery interval” is first successful delivery after fault, not proof of route reactivation. Routing-control overhead is not fully measured (probe bytes excluded); AODV per-packet hops are not instrumented. Energy is neither measured nor estimated. Results do not establish broad ML superiority.

Complementary packet-loss rates (AODV / tree): healthy **0.0007 / 0.0400**, degraded reliability **0.7100 / 0.3071**, increased latency **0.0014 / 0.0329**, relay failure **0.0014 / 0.0200**. On relay failure, first-delivery recovery interval was **0.109 ± 0.240 s** for AODV and **2.954 ± 4.031 s** for the tree; high variance and the metric limitation above apply.

The simpler root Python simulator's `results/python/aggregate_results.csv` is a separate experiment and must not be conflated with INET/AODV results.

## Live API compatibility

Streamlit keeps simulation, live API, and persisted historical records separate. The live tab shows source node, gateway, server `receivedAt`, dashboard fetch time, and now API connection state; it is read-only. Gateway telemetry includes `rssiDbm`, `latencyMs`, `packetLossPercent`, `throughputBps`, `hopCount`, `nextHopId`, and forwarding/source IDs.

These records do **not** match embedded tree input. API currently lacks per-candidate upper/lower route availability, path PDR estimates, path latency and hop counts, neighbor status, and recent transmission-failure counts. It records the chosen packet path, not simultaneous alternatives. Its one-record RSSI/latency/loss/throughput cannot safely be expanded into the eight route-choice features. No live inference feature builder is enabled; missing values are not fabricated. Collect candidate-link windows and route-level outcomes (including unavailable/no-route cases) before training or integrating live routing.

## Files changed in Step 2

- `docs/machine_learning/evaluation.md` — corrected stale failure-recall statement and model-use limits.
- `docs/machine_learning/step2_validation_report.md` — this audit and deployment-prep report.
- `simulation/inet/ml-routing/tests/test_route_ml.py` — grouped CV and held-out no-route detection guard.
- `app.py` — explicit connected/unavailable/not-checked state and last successful API fetch timestamp.

No firmware, model binaries, trained model artifact, dataset, historical simulation result, API route, or database was changed. Stop here; firmware ML integration is Step 3.
