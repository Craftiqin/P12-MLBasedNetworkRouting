import csv
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


@unittest.skipUnless(shutil.which("inet") and os.environ.get("INET_ROOT"), "activate OMNeT++ and INET before integration tests")
class MlRoutingIntegrationTests(unittest.TestCase):
    def run_config(self, config):
        result = subprocess.run(
            [sys.executable, "tools/run_ml_experiment.py", "--config", config],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        match = re.search(r"validated: (.+)", result.stdout)
        self.assertIsNotNone(match, result.stdout + result.stderr)
        run_dir = Path(match.group(1))
        with (run_dir / "events.csv").open(newline="") as stream:
            events = list(csv.DictReader(stream))
        metrics = json.loads((run_dir / "metrics.json").read_text())
        stdout = (run_dir / "stdout.log").read_text()
        return events, metrics, run_dir, stdout

    def test_model_decision_changes_forwarding_and_completes_multihop_delivery(self):
        events, metrics, run_dir, stdout = self.run_config("MLRoutePreference")
        decisions = [row for row in events if row["event"] == "decision"]
        self.assertEqual(len(decisions), 280)
        self.assertTrue(all(row["predicted_route"] == row["selected_route"] == "lower" for row in decisions))
        self.assertEqual(metrics["packets_generated"], 280)
        self.assertEqual(metrics["packets_received_unique"], 280)
        self.assertEqual(metrics["pdr"], 1.0)
        self.assertEqual(metrics["mean_packet_hops"], 3)
        self.assertEqual(metrics["valid_delivered_path_count"], 280)
        self.assertEqual(metrics["delivered_path_errors"], [])
        self.assertEqual(metrics["loop_drops"], 0)
        for marker in ("[ML-STATUS]", "[ML-INFERENCE]", "[ML-PREDICTION]", "[ROUTE-SELECTION]",
                       "[PACKET-FORWARD]", "[PACKET-DELIVERED]", "[ML-SUMMARY]",
                       "PACKET event=generated", "PACKET event=received", "PACKET event=forwarded",
                       "PACKET event=delivered", "ROUTE_CHANGED"):
            self.assertIn(marker, stdout)
        self.assertIn("feature_order=upper_available,upper_pdr_estimate,upper_latency_ms,upper_hops,lower_available,lower_pdr_estimate,lower_latency_ms,lower_hops", stdout)
        self.assertIn("prediction_matches_selection=true", stdout)
        self.assertIn("selected_next_hop=node[4]", stdout)
        self.assertIn("packets_delivered=280", stdout)
        with (run_dir / "ml_decision_trace.csv").open(newline="") as stream:
            trace = list(csv.DictReader(stream))
        self.assertEqual(len(trace), 280)
        self.assertTrue(all(row["prediction"] == "lower" for row in trace))
        self.assertTrue(all(row["selected_next_hop"] == "node[4]" for row in trace))
        self.assertTrue(all(row["forwarded"] == "true" and row["delivered"] == "true" for row in trace))
        self.assertTrue(all(row["relay_forwards"] == "2" for row in trace))
        self.assertIn("Packet-level ML decision trace", (run_dir / "dashboard" / "index.html").read_text())
        metrics = json.loads((run_dir / "metrics.json").read_text())
        self.assertEqual(metrics["ml_inference_calls"], 280)
        self.assertEqual(metrics["valid_predictions"], 280)
        self.assertEqual(metrics["rejected_predictions"], 0)
        self.assertEqual(metrics["fallback_decisions"], 0)
        self.assertEqual(metrics["source_handoffs"], 280)
        self.assertEqual(metrics["packets_forwarded_at_relays"], 560)
        summary = re.search(r"\[ML-SUMMARY\].*mean_delay_ms=([0-9.]+).*mean_packet_hops=([0-9.]+)", stdout)
        self.assertIsNotNone(summary, stdout[-2000:])
        self.assertAlmostEqual(float(summary.group(1)), metrics["mean_delay_ms"], places=2)
        self.assertAlmostEqual(float(summary.group(2)), metrics["mean_packet_hops"], places=6)
        dashboard = run_dir / "dashboard"
        self.assertTrue((dashboard / "index.html").is_file())
        for chart in ("01-pdr.svg", "02-delay.svg", "03-throughput.svg", "04-hop-count.svg",
                      "05-route-recovery.svg", "06-delivery-timeline.svg"):
            self.assertTrue((dashboard / chart).is_file(), chart)

    def test_failed_relay_is_rejected_and_alternate_route_recovers_delivery(self):
        events, metrics, _, stdout = self.run_config("MLPreferredPathFailure")
        after_failure = [row for row in events if row["event"] == "decision" and 30 <= float(row["time_s"]) < 58]
        self.assertTrue(after_failure)
        self.assertTrue(all(row["upper_available"] == "0" for row in after_failure))
        self.assertTrue(all(row["selected_route"] == "lower" and row["next_hop_id"] == "4" for row in after_failure))
        self.assertTrue(all(row["fallback"] == "1" for row in after_failure))
        self.assertIsNotNone(metrics["route_recovery_s"])
        self.assertEqual(metrics["pdr"], 1.0)
        self.assertIn("FAILURE_DETECTED", stdout)
        self.assertIn("ROUTE_CHANGED", stdout)

    def test_no_valid_route_drops_and_records_instead_of_forwarding(self):
        events, metrics, _, stdout = self.run_config("MLNoRoute")
        decisions = [row for row in events if row["event"] == "decision" and float(row["time_s"]) >= 3]
        drops = [row for row in events if row["event"] == "no_route_drop"]
        self.assertTrue(decisions)
        self.assertTrue(all(row["selected_route"] == "none" and row["next_hop_id"] == "-1" for row in decisions))
        self.assertTrue(all(row["fallback"] == "1" for row in decisions))
        self.assertTrue(drops)
        self.assertEqual(metrics["packets_generated"], 280)
        self.assertGreater(metrics["packets_lost_by_end"], 0)
        self.assertIn("PACKET event=dropped", stdout)

    def test_restarted_relay_requires_probe_and_remains_ineligible_without_path_proof(self):
        events, metrics, _, stdout = self.run_config("MLLinkRecovery")
        up = [row for row in events if row["event"] == "path_status_up" and row["route"] == "upper"]
        probes = [row for row in events if row["event"] == "path_probe_sent" and row["route"] == "upper"]
        proof = [row for row in events if row["event"] == "path_probe_success" and row["route"] == "upper"]
        decisions_after_restart = [row for row in events if row["event"] == "decision" and float(row["time_s"]) >= 45]
        self.assertTrue(up)
        self.assertTrue(probes)
        self.assertFalse(proof)
        self.assertTrue(all(row["upper_available"] == "0" for row in decisions_after_restart))
        self.assertFalse(metrics["recovered_path_eligible"])
        self.assertIn("PATH_STATUS_UP", stdout)
        self.assertIn("ROUTE_PROBE_SENT", stdout)


if __name__ == "__main__":
    unittest.main()
