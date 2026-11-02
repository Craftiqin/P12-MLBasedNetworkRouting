# Report validation summary

## Evidence reviewed
- Current repository source: `simulator/core.py`, `routing/engines.py`, `ml/pipeline.py`, `experiments/runner.py`, `metrics/core.py`.
- INET ML implementation: `simulation/inet/ml-routing/src/p12ganesh/mesh/MeshRoutingApp.cc`, model training/export, generated C++ header, scenario configuration, README, and unit/integration tests.
- Existing project report and source documentation/diagrams.
- Fresh seed-17 model and simulation outputs retained in `evidence/`.

## Fresh results
- Dataset: 5400 synthetic observations; 60 runs × 90 observations; split by complete run IDs, 45 train / 15 test. Test condition only: strong.
- INET route tree: 600 synthetic rows; 480 train / 120 held out; accuracy 0.9667; macro F1 0.9677; C++ header parity test passed.
- Python link classifier accuracy: 0.9526; success precision 0.9618; success recall 0.9900; failure recall 0.0377; ROC AUC 0.7184.
- Network: 5 paired trials, 100 packets, 7 scenarios, 2 Python policies; 70 policy-trial rows. See raw and aggregate CSV.
- Tests: root pytest → 9 passed; INET/ML unittest → 11 passed, 4 skipped. C++ generated header parity compiled with clang++ and passed; 4 live INET integration cases skipped because `inet` and `INET_ROOT` were unavailable.

## Claim boundaries
- Python results are abstract graph-simulation outcomes with synthetic/configured link data.
- C++ `MeshRoutingApp` and generated Decision Tree header exist. Runtime integration cases skipped this session; no .sca/.vec/.rt outputs retained. No AODV metrics claimed.
- Hardware diagram is a design concept. No firmware, assembled prototype, measured radio or energy data found.
- The 96.7% classifier checkpoint is verified by current synthetic model JSON (96.67%, 120 held-out rows). 280/280 and three hops occur as skipped integration-test assertions, not retained runtime data; delay/recovery checkpoints and 14/14 lack corroborating artifacts.
- Student/institution/signatory fields remain explicit placeholders because source identity details were unavailable.

## Deliverable checks
- New DOCX is separate from original report. PDF is rendered from this DOCX.
- DOCX contains all ten requested chapters, preliminary pages, references, and reproducibility appendices.
- Figures include Python and INET architecture, hardware concept, model workflow, Python topology, and fresh Python PDR/latency charts.
