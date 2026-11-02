#!/usr/bin/env python3
"""Create a transparent single-pair AODV/ML metric comparison."""

import argparse
import csv
import json
from pathlib import Path


def load_pair(aodv_dir: Path, ml_dir: Path):
    summary_path = aodv_dir / "dashboard" / "summary.json"
    if not summary_path.exists():
        # Failure dashboards may use an explicitly versioned output directory.
        candidates = sorted(aodv_dir.glob("dashboard-*/summary.json"))
        if not candidates:
            raise FileNotFoundError(f"No dashboard summary in {aodv_dir}")
        summary_path = candidates[-1]
    aodv = json.loads(summary_path.read_text())
    ml = json.loads((ml_dir / "metrics.json").read_text())
    aodv_manifest = json.loads((aodv_dir / "manifest.json").read_text())
    ml_manifest = json.loads((ml_dir / "manifest.json").read_text())
    if aodv_manifest.get("seed_set") != ml_manifest.get("seed_set"):
        raise ValueError("paired runs must use identical seed sets")
    aodv_traffic = aodv_manifest.get("application_traffic", {})
    ml_traffic = ml_manifest.get("application_traffic", {})
    if aodv_traffic != ml_traffic:
        raise ValueError("paired runs must use identical packet size and traffic window")
    metrics = [
        ("Packets generated", aodv.get("generated_unique_application_packets"), ml.get("packets_generated"), "packets"),
        ("Unique packets received", aodv.get("received_unique_application_packets"), ml.get("packets_received_unique"), "packets"),
        ("Packet delivery ratio", aodv.get("packet_delivery_ratio"), ml.get("pdr"), "ratio"),
        ("Packet loss", aodv.get("not_received_by_end"), ml.get("packets_lost_by_end"), "packets"),
        ("Mean end-to-end delay", aodv.get("mean_end_to_end_delay_s", 0) * 1000, ml.get("mean_delay_ms"), "ms"),
        ("Throughput", aodv.get("throughput_bps"), ml.get("throughput_bit_s"), "bit/s"),
        ("Mean packet-level hops", aodv.get("packet_level_hop_count"), ml.get("mean_packet_hops"), "hops"),
        ("Route changes", aodv.get("route_change_events"), ml.get("route_changes"), "changes"),
        ("Route recovery interval", aodv.get("route_recovery_time_s"), ml.get("route_recovery_s"), "s"),
        ("Routing control overhead", aodv.get("routing_control_overhead"), ml.get("routing_control_overhead"), "bytes"),
        ("Duplicate drops", aodv.get("duplicate_receive_events"), ml.get("duplicate_drops"), "packets"),
        ("Hop-limit drops", "Not measured", ml.get("hop_limit_drops"), "packets"),
    ]
    return metrics, aodv, ml, aodv_manifest, ml_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aodv-run", type=Path, required=True)
    parser.add_argument("--ml-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    metrics, aodv, ml, am, mm = load_pair(args.aodv_run, args.ml_run)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    csv_path = args.output_dir / "comparison.csv"
    with csv_path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["metric", "AODV", "Decision Tree", "unit"])
        writer.writerows(metrics)
    lines = [
        "# AODV vs Decision Tree routing",
        "",
        f"- AODV run: `{args.aodv_run}` ({aodv['config']})",
        f"- ML run: `{args.ml_run}` ({mm['config']})",
        f"- Matched seed set: `{am['seed_set']}`; payload, interval, and traffic window checked from manifests.",
        f"- ML provenance: {ml['data_origin']}.",
        "- Single deterministic run per arm; no repeated-run confidence interval. Features are configured route estimates plus actual runtime relay availability; estimates are not measured link PDR/latency.",
        "- Treat performance differences as observed for this application-level forwarding implementation; they do not establish general ML superiority.",
        "",
        "| Metric | AODV | Decision Tree | Unit |",
        "|---|---:|---:|---|",
    ]
    for name, av, mv, unit in metrics:
        lines.append(f"| {name} | {av if av is not None else 'Not measured'} | {mv if mv is not None else 'Not measured'} | {unit} |")
    (args.output_dir / "comparison.md").write_text("\n".join(lines) + "\n")
    print(csv_path)
    print(args.output_dir / "comparison.md")


if __name__ == "__main__":
    main()
