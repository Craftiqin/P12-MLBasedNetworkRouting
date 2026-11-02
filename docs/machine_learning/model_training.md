# Model training

`python train_model.py` calls `train_model()` using defaults (60 runs, seed 17). Tree: `DecisionTreeClassifier(max_depth=6, min_samples_leaf=8, class_weight="balanced", random_state=seed)`. Evaluation split uses complete run IDs: first 75% train, remainder test; default synthetic conditions are grouped by run ranges. Evaluation reports accuracy, success and failure precision/recall/F1, confusion matrix, ROC-AUC when both classes exist, inference time, run IDs and conditions. Re-run `python -m pytest -q` for regression checks.

Artifacts under `ml/data/synthetic/` and `ml/models/`. Report exact seed, run count and metrics JSON with any analysis. The included model is an older generated artifact; metadata is authoritative for that artifact, not a guarantee a fresh training run matches every metric after dependency/version changes.
