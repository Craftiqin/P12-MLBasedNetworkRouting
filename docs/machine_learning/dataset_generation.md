# Dataset generation

`ml/pipeline.py::generate_dataset(runs=60, seed=17, node_count=6)` samples existing topology edges for four synthetic conditions (`normal`, `degraded`, `busy`, `strong`). It synthesizes RSSI, loss, latency and congestion with seeded NumPy draws; target is a fresh Bernoulli one-link outcome. Rows contain `run_id`, condition and synthetic marker. No packet traces, live ACKs, INET vectors or radio measurements are ingested.

Run `python train_model.py` from root to regenerate dataset and train. For exact custom data generation, import `generate_dataset(runs=..., seed=...)`. Changing `runs` changes condition grouping due integer partitioning; retain seed and parameters with each reported result. Dataset is generated output, so Git ignores replacements; only small published snapshot is currently checked in.
