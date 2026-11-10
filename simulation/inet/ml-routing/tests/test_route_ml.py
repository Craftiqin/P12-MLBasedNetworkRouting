import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from sklearn.metrics import confusion_matrix, recall_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.tree import DecisionTreeClassifier

from ml.generate_route_dataset import generate_rows, write_dataset
from ml.route_metrics import summarize
from ml.route_policy import select_safely
from ml.train_tree import FEATURES, train

ROOT = Path(__file__).parents[1]


class RouteMlTests(unittest.TestCase):
    def test_dataset_is_reproducible_and_seed_split_disjoint(self):
        first = generate_rows(run_count=10, seed=42)
        second = generate_rows(run_count=10, seed=42)
        self.assertEqual(first, second)
        train_ids = {row["seed"] for row in first if row["split"] == "train"}
        test_ids = {row["seed"] for row in first if row["split"] == "test"}
        self.assertFalse(train_ids & test_ids)
        self.assertTrue(all(row["data_origin"] == "synthetic_controlled_route_scenario" for row in first))

    def test_training_evaluates_held_out_rows_and_exports_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "routes.csv"
            write_dataset(data, run_count=20, seed=8)
            metrics, _ = train(data, root / "tree.json", root / "metrics.json", root / "DecisionTreeModel.h")
            model = json.loads((root / "tree.json").read_text())
            self.assertEqual(metrics["test_rows"], 24)
            self.assertGreaterEqual(metrics["accuracy"], 0.75)
            self.assertIn("synthetic", model["metadata"]["data_origin"])
            self.assertTrue((root / "DecisionTreeModel.h").exists())

    def test_grouped_validation_and_no_route_failure_detection(self):
        with (ROOT / "ml" / "data" / "route_scenarios.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        training = [row for row in rows if row["split"] == "train"]
        testing = [row for row in rows if row["split"] == "test"]
        x_train = [[float(row[name]) for name in FEATURES] for row in training]
        y_train = [int(row["label_route"]) for row in training]
        groups = [int(row["seed"]) for row in training]
        model = DecisionTreeClassifier(max_depth=4, min_samples_leaf=3, random_state=20261101)
        cv_predictions = cross_val_predict(
            model, x_train, y_train, groups=groups, cv=GroupKFold(n_splits=5)
        )
        self.assertGreaterEqual(recall_score(y_train, cv_predictions, labels=[-1], average="micro"), 0.95)
        self.assertEqual(confusion_matrix(y_train, cv_predictions, labels=[-1, 0, 1])[0, 1:].sum(), 0)

        model.fit(x_train, y_train)
        no_route = [row for row in testing if int(row["label_route"]) == -1]
        self.assertTrue(no_route)
        x_no_route = [[float(row[name]) for name in FEATURES] for row in no_route]
        self.assertTrue(all(prediction == -1 for prediction in model.predict(x_no_route)))

    def test_invalid_prediction_uses_safe_fallback(self):
        features = {
            "upper_available": 0,
            "upper_pdr_estimate": 0.99,
            "upper_latency_ms": 10,
            "upper_hops": 3,
            "lower_available": 1,
            "lower_pdr_estimate": 0.9,
            "lower_latency_ms": 25,
            "lower_hops": 3,
        }
        self.assertEqual(select_safely(0, features), 1)
        self.assertEqual(select_safely(77, features), 1)
        features["lower_available"] = 0
        self.assertEqual(select_safely(77, features), -1)

    def test_missing_or_invalid_features_never_select_bad_candidate(self):
        features = {
            "upper_available": 1,
            "upper_pdr_estimate": float("nan"),
            "upper_latency_ms": 10,
            "upper_hops": 3,
            "lower_available": 1,
            "lower_pdr_estimate": 0.9,
            "lower_latency_ms": 30,
            "lower_hops": 3,
        }
        self.assertEqual(select_safely(0, features), 1)
        del features["lower_latency_ms"]
        self.assertEqual(select_safely(0, features), -1)

    def test_metrics_use_per_packet_rows(self):
        result = summarize([
            {"packet_id": 1, "created_s": 1.0, "received_s": 1.1, "received": True,
             "hops": 3, "payload_bytes": 100, "control_packets": 2},
            {"packet_id": 2, "created_s": 2.0, "received_s": 2.4, "received": True,
             "hops": 4, "payload_bytes": 100, "control_packets": 1},
            {"packet_id": 3, "created_s": 3.0, "received": False,
             "hops": 0, "payload_bytes": 100, "duplicate_drops": 1, "hop_limit_drops": 1},
        ], observation_seconds=2.0, failure_time_s=2.5, route_recovery_s=0.3)
        self.assertEqual(result["packets_sent"], 3)
        self.assertEqual(result["packets_received"], 2)
        self.assertAlmostEqual(result["pdr"], 2 / 3)
        self.assertAlmostEqual(result["mean_end_to_end_delay_s"], 0.25)
        self.assertEqual(result["mean_packet_hops"], 3.5)
        self.assertEqual(result["routing_control_packets"], 3)
        self.assertEqual(result["duplicate_drops"], 1)
        self.assertEqual(result["hop_limit_drops"], 1)
        self.assertEqual(result["route_recovery_s"], 0.3)

    def test_generated_cpp_matches_python_heldout_and_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = ROOT / "ml" / "data" / "route_scenarios.csv"
            _, model = train(data, root / "tree.json", root / "metrics.json", root / "DecisionTreeModel.h")
            with data.open(newline="") as stream:
                rows = [row for row in csv.DictReader(stream) if row["split"] == "test"]
            test_x = [[float(row[name]) for name in FEATURES] for row in rows]
            expected = model.predict(test_x).astype(int).tolist()
            cpp_samples = "\n".join(
                "    std::cout << predict(RouteFeatures{" + ",".join(format(x, ".17g") for x in sample) + "}) << '\\n';"
                for sample in test_x
            )
            source = root / "smoke.cc"
            source.write_text(f'''#include "{root / 'DecisionTreeModel.h'}"
#include <cassert>
#include <cmath>
#include <iostream>
#include <string>
int main() {{
    using namespace p12ganesh::ml;
    assert(std::string(MODEL_VERSION) == "decision-tree-v1-seed-20261101");
{cpp_samples}
    RouteFeatures invalidUpper{{1, NAN, 10, 3, 1, .8, 80, 3}};
    assert(predict(invalidUpper) == -2);
    assert(selectSafely(-2, invalidUpper) == 1);
    invalidUpper.lower_available = 0;
    assert(selectSafely(-2, invalidUpper) == -1);
    RouteFeatures upperUnavailable{{0, 0, 1000, 3, 1, .95, 56, 3}};
    assert(selectSafely(0, upperUnavailable) == 1);
    RouteFeatures lowerUnavailable{{1, .9, 31, 3, 0, 0, 1000, 3}};
    assert(selectSafely(1, lowerUnavailable) == 0);
}}
''')
            exe = root / "smoke"
            subprocess.run(["clang++", "-std=c++17", str(source), "-o", str(exe)], check=True, capture_output=True)
            output = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout
            self.assertEqual([int(line) for line in output.splitlines()], expected)


if __name__ == "__main__":
    unittest.main()
