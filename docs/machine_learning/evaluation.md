# Evaluation and known limitations

See [Step 2 validation report](step2_validation_report.md) for current checked-in artifact metrics, grouped cross-validation, embedded C++ parity, paired INET/AODV results, and live API gaps.

The root `ml/models/delivery_tree.joblib` predicts a **single synthetic link-attempt ACK outcome**, not a next-hop route. Fresh default evaluation (60 runs, seed 17) has 95.26% accuracy but only **3.77% failure recall**; its held-out split contains only the `strong` condition. Do not use it for ESP32 routing.

The separate INET route-choice tree is a compact candidate for later embedded integration. It is trained on synthetic controlled path estimates, not physical measurements. Its no-route detection is supported by few held-out examples; a high score on this generator does not establish real-radio reliability. Live telemetry currently lacks candidate-specific route metrics required by that model. No physical ML routing, energy measurement, or ESP32 inference benchmark has been demonstrated.

Historical datasets and simulation outputs are retained. Re-run reports into a new output directory when preserving prior evidence matters; do not overwrite historical run artifacts.
