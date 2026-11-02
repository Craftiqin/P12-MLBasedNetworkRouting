#!/usr/bin/env python3
"""Run sequential matched AODV/ML trials and summarize per-seed metrics."""

import argparse
import csv
import json
import re
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = {
    "healthy": ("Normal", "MLRouting"),
    "degraded_reliability": ("AODVDegradedReliability", "MLDegradedReliability"),
    "increased_latency": ("AODVIncreasedLatency", "MLIncreasedLatency"),
    "relay_failure": ("AODVPreferredPathFailure", "MLPreferredPathFailure"),
    "relay_recovery": ("AODVLinkRecovery", "MLLinkRecovery"),
}


def run(command, log_path):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    log_path.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}); see {log_path}\n{result.stderr[-2000:]}")
    return result.stdout


def run_dir(stdout, pattern):
    match = re.search(pattern, stdout)
    if not match:
        raise RuntimeError(f"Could not find run directory in output:\n{stdout[-2000:]}")
    return Path(match.group(1).strip())


def load_metrics(aodv_dir, ml_dir):
    aodv = json.loads((aodv_dir / "dashboard" / "summary.json").read_text())
    ml = json.loads((ml_dir / "metrics.json").read_text())
    return {
        "aodv_pdr": aodv.get("packet_delivery_ratio"), "ml_pdr": ml.get("pdr"),
        "aodv_delay_ms": (aodv.get("mean_end_to_end_delay_s") or 0) * 1000,
        "ml_delay_ms": ml.get("mean_delay_ms"),
        "aodv_throughput_bit_s": aodv.get("throughput_bps"), "ml_throughput_bit_s": ml.get("throughput_bit_s"),
        "aodv_hops": aodv.get("packet_level_hop_count"), "ml_hops": ml.get("mean_packet_hops"),
        "aodv_recovery_s": aodv.get("route_recovery_time_s"), "ml_recovery_s": ml.get("route_recovery_s"),
        "aodv_route_changes": aodv.get("route_change_events"), "ml_route_changes": ml.get("route_changes"),
        "aodv_routing_control_overhead": aodv.get("routing_control_overhead", "Not measured"),
        "ml_routing_control_overhead": ml.get("routing_control_overhead", "Not measured"),
    }


def aggregate(values):
    result = {}
    for key in values[0]:
        numeric = [float(row[key]) for row in values if isinstance(row[key], (int, float))]
        result[key + "_mean"] = statistics.mean(numeric) if numeric else None
        result[key + "_sd"] = statistics.stdev(numeric) if len(numeric) > 1 else (0.0 if numeric else None)
        result[key + "_n"] = len(numeric)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=[17, 18, 19, 20, 21])
    parser.add_argument("--conditions", nargs="+", choices=CONDITIONS, default=list(CONDITIONS))
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = ROOT / "experiments" / "comparisons" / f"{stamp}-repeated"
    suffix = 1
    while output.exists():
        output = ROOT / "experiments" / "comparisons" / f"{stamp}-{suffix}-repeated"
        suffix += 1
    output.mkdir(parents=True)
    rows = []
    for condition in args.conditions:
        aodv_config, ml_config = CONDITIONS[condition]
        for seed in args.seeds:
            stem = f"{condition}-seed{seed}"
            ml_stdout = run([sys.executable, "tools/run_ml_experiment.py", "--config", ml_config,
                             "--seed-set", str(seed)], output / f"{stem}-ml-runner.log")
            ml_dir = run_dir(ml_stdout, r"validated: (.+)")
            aodv_stdout = run([sys.executable, "tools/run_aodv_experiment.py", "--ui", "Cmdenv",
                               "--config", aodv_config, "--seed-set", str(seed)],
                              output / f"{stem}-aodv-runner.log")
            aodv_dir = run_dir(aodv_stdout, r"Raw result files and manifest: (.+)")
            am = json.loads((aodv_dir / "manifest.json").read_text())
            mm = json.loads((ml_dir / "manifest.json").read_text())
            if am["seed_set"] != mm["seed_set"] or am["application_traffic"] != mm["application_traffic"]:
                raise RuntimeError(f"Unmatched AODV/ML trial: {stem}")
            metrics = load_metrics(aodv_dir, ml_dir)
            rows.append({"condition": condition, "seed_set": seed, "aodv_config": aodv_config,
                         "ml_config": ml_config, "aodv_run": str(aodv_dir), "ml_run": str(ml_dir), **metrics})
            print(f"{condition} seed={seed}: AODV PDR={metrics['aodv_pdr']} ML PDR={metrics['ml_pdr']}", flush=True)

    with (output / "trial_results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    by_condition = {}
    for condition in args.conditions:
        condition_rows = [row for row in rows if row["condition"] == condition]
        numeric = [{key: value for key, value in row.items() if key.endswith(("_pdr", "_delay_ms", "_throughput_bit_s", "_hops", "_recovery_s", "_route_changes"))}
                   for row in condition_rows]
        by_condition[condition] = aggregate(numeric)
    (output / "aggregate_results.json").write_text(json.dumps(by_condition, indent=2) + "\n")
    lines = ["# Repeated matched AODV vs Decision Tree experiments", "",
             f"Seeds: {', '.join(map(str, args.seeds))}; paired topology, traffic, and seed-set checked from manifests.",
             "Each cell reports mean ± sample SD across runs (where at least two values exist).",
             "Configured PDR/latency values are model input estimates, not live observations. Degraded-reliability condition adds a heavy competing UDP flow and shared-medium interference; increased latency uses lower PHY bitrate.",
             "AODV packet-level hops and routing control overhead are not instrumented. ML control overhead currently excludes active probe byte cost and is therefore not measured.",
             "Single platform only; these trials do not prove general ML superiority.", ""]
    for condition, values in by_condition.items():
        lines += [f"## {condition}", "", "| Metric | AODV mean ± SD | ML mean ± SD |", "|---|---:|---:|"]
        metrics = (("PDR", "aodv_pdr", "ml_pdr"), ("Delay (ms)", "aodv_delay_ms", "ml_delay_ms"),
                   ("Throughput (bit/s)", "aodv_throughput_bit_s", "ml_throughput_bit_s"),
                   ("Packet hops", "aodv_hops", "ml_hops"), ("Recovery (s)", "aodv_recovery_s", "ml_recovery_s"))
        for label, akey, mkey in metrics:
            amean, asd = values.get(akey + "_mean"), values.get(akey + "_sd")
            mmean, msd = values.get(mkey + "_mean"), values.get(mkey + "_sd")
            fmt = lambda mean, sd: "Not measured" if mean is None else f"{mean:.5g} ± {sd:.3g}"
            lines.append(f"| {label} | {fmt(amean, asd)} | {fmt(mmean, msd)} |")
        lines.append("")
    (output / "report.md").write_text("\n".join(lines))
    print(f"Repeated trial results: {output}")


if __name__ == "__main__":
    main()
