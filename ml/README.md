# ML and Python simulation

Pipeline in `pipeline.py` generates synthetic per-link ACK observations, trains a Decision Tree, evaluates on held-out complete run IDs, writes data/model/JSON metadata, then `routing/engines.py` applies next-hop probability-cost scoring inside the separate Python graph simulator.

Feature columns: `rssi_dbm`, `latency_ms`, `loss_estimate`, `throughput_kbps`, `remaining_hops`; target `delivery_success` (one-hop synthetic ACK outcome). Dataset uses four generated conditions and Bernoulli labels derived from generated loss/congestion. All records are synthetic; there are no simulation- or hardware-measured observations. Training uses first 75% run IDs; test uses final 25%, which are condition-grouped under default generation. Same seed yields reproducible data/split, but training seed and experiment trial seeds are not identical data. Experiments fit model with suite seed, then compare routes with paired trial seeds.

## Setup and commands

Use [ML installation guide](../docs/installation/ML_SETUP.md), then from repo root:

```sh
python train_model.py
python run_experiments.py --trials 5 --packets 100 --seed 17 --nodes 6
python -m pytest -q
```

Artifacts: `ml/data/synthetic/link_observations.csv`, `ml/models/delivery_tree.joblib`, `ml/models/delivery_tree.json`. Evaluation metrics in JSON include both class scores, confusion matrix, ROC-AUC where defined and split IDs/conditions. Do not summarize by accuracy alone. Current included artifact has failure recall 0.0.

## Integration and limits

Model controls candidate selection only in `simulator/core.py` through Python `predict_proba`; it does not control INET AODV or hardware. See [integration status](../docs/machine_learning/model_integration.md), [dataset details](../docs/machine_learning/dataset_generation.md), [evaluation](../docs/machine_learning/evaluation.md). Exported JSON is metadata, not a portable C++ inference model.
