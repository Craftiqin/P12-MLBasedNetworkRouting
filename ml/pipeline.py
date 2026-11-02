from __future__ import annotations

import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.tree import DecisionTreeClassifier

from simulator.core import FEATURES, build_topology, link_features


def generate_dataset(runs: int = 60, seed: int = 17, node_count: int = 6) -> pd.DataFrame:
    """Synthetic ACK observations, grouped by independent simulation run."""
    rng = np.random.default_rng(seed)
    rows = []
    conditions = [("normal", -60, .03, 18), ("degraded", -84, .35, 55),
                  ("busy", -70, .20, 42), ("strong", -48, .01, 12)]
    graph = build_topology(node_count)
    edges = list(graph.edges(data=True))
    for run_id in range(runs):
        condition, rssi, loss, latency = conditions[(run_id // max(1, runs // 4)) % len(conditions)]
        run_bias = rng.normal(0, 4)
        for obs in range(90):
            _, _, edge = edges[int(rng.integers(len(edges)))]
            sample_loss = float(np.clip(loss + rng.normal(0, .07), 0, .9))
            sample_rssi = float(np.clip(rssi + run_bias + rng.normal(0, 5), -100, -35))
            sample_latency = float(max(1, latency + rng.normal(0, 12)))
            congestion = float(np.clip(rng.beta(2, 5) * (condition == "busy"), 0, .9))
            attrs = {**edge, "rssi_dbm":sample_rssi, "loss_probability":sample_loss,
                     "latency_ms":sample_latency, "congestion":congestion}
            distance = int(rng.integers(0, 5))
            features = link_features(attrs, distance, congestion)
            # Labels come from independent Bernoulli transmission outcomes, never model scores.
            delivery_success = int(rng.random() >= min(.98, sample_loss + congestion * .25))
            rows.append(dict(zip(FEATURES, features), delivery_success=delivery_success,
                             run_id=run_id, condition=condition, synthetic=True))
    return pd.DataFrame(rows)


def train_model(*, runs: int = 60, seed: int = 17, data_path: str | Path = "ml/data/synthetic/link_observations.csv",
                model_path: str | Path = "ml/models/delivery_tree.joblib") -> tuple[DecisionTreeClassifier, dict, pd.DataFrame]:
    data = generate_dataset(runs, seed)
    # Hold out complete runs and conditions; no row-level random split leakage.
    boundary = max(1, int(runs * .75))
    train = data[data.run_id < boundary]
    test = data[data.run_id >= boundary]
    if train.delivery_success.nunique() < 2:
        raise ValueError("training data contains only one target class")
    clf = DecisionTreeClassifier(max_depth=6, min_samples_leaf=8, class_weight="balanced", random_state=seed)
    clf.fit(train[FEATURES], train.delivery_success)
    start = time.perf_counter()
    predicted = clf.predict(test[FEATURES])
    elapsed_ms = (time.perf_counter() - start) * 1000 / max(1, len(test))
    probs = clf.predict_proba(test[FEATURES])[:, list(clf.classes_).index(1)]
    metrics = {"accuracy":float(accuracy_score(test.delivery_success, predicted)),
               "precision":float(precision_score(test.delivery_success, predicted, zero_division=0)),
               "recall":float(recall_score(test.delivery_success, predicted, zero_division=0)),
               "f1":float(f1_score(test.delivery_success, predicted, zero_division=0)),
               "failure_precision":float(precision_score(test.delivery_success,predicted,pos_label=0,zero_division=0)),
               "failure_recall":float(recall_score(test.delivery_success,predicted,pos_label=0,zero_division=0)),
               "failure_f1":float(f1_score(test.delivery_success,predicted,pos_label=0,zero_division=0)),
               "confusion_matrix":confusion_matrix(test.delivery_success, predicted, labels=[0,1]).tolist(),
               "roc_auc":float(roc_auc_score(test.delivery_success, probs)) if test.delivery_success.nunique() == 2 else None,
               "inference_ms_per_observation":elapsed_ms,
               "train_runs":sorted(train.run_id.unique().tolist()),
               "test_runs":sorted(test.run_id.unique().tolist()),
               "train_conditions":sorted(train.condition.unique().tolist()),
               "test_conditions":sorted(test.condition.unique().tolist()),
               "features":FEATURES,"target":"delivery_success: ACK within one simulated link attempt",
               "data_kind":"synthetic simulation data","seed":seed,
               "class_counts":{str(k):int(v) for k,v in data.delivery_success.value_counts().items()}}
    data_path, model_path = Path(data_path), Path(model_path)
    data_path.parent.mkdir(parents=True, exist_ok=True); model_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(data_path, index=False)
    import joblib
    joblib.dump(clf, model_path)
    model_path.with_suffix(".json").write_text(json.dumps(metrics, indent=2))
    return clf, metrics, data


def load_model(path: str | Path = "ml/models/delivery_tree.joblib"):
    import joblib
    return joblib.load(path)
