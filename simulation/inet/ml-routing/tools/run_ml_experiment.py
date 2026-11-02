#!/usr/bin/env python3
"""Run one Decision Tree configuration into a unique, validated results folder."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.analyze_runtime_trace import analyze  # noqa: E402

CONFIGS = {"MLRouting", "MLRoutePreference", "MLPreferredPathFailure", "MLNoRoute", "MLLinkRecovery",
           "MLDegradedReliability", "MLIncreasedLatency"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", choices=sorted(CONFIGS), default="MLRouting")
    parser.add_argument("--seed-set", type=int, default=17)
    args = parser.parse_args()
    inet_root = os.environ.get("INET_ROOT")
    inet = shutil.which("inet")
    if not inet or not inet_root:
        raise SystemExit("Activate OMNeT++ and INET setenv scripts before running this command")
    if shutil.disk_usage(ROOT).free < 512 * 1024 * 1024:
        raise SystemExit("Refusing to start: less than 512 MiB free disk space")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = ROOT / "experiments" / "runs"
    run_dir = base / f"{stamp}-ML-{args.config}"
    suffix = 1
    while run_dir.exists():
        run_dir = base / f"{stamp}-ML-{args.config}-{suffix}"
        suffix += 1
    run_dir.mkdir(parents=True)
    events = run_dir / "events.csv"
    sca = run_dir / f"{args.config}.sca"
    vec = run_dir / f"{args.config}.vec"
    failure_time = {"MLPreferredPathFailure": 30.0, "MLLinkRecovery": 30.0, "MLNoRoute": 3.0}.get(args.config)
    restart_time = 45.0 if args.config == "MLLinkRecovery" else None

    library_names = ("libmesh.dylib", "libmesh.so", "libmesh.dll", "mesh.dll")
    library = next((ROOT / name for name in library_names if (ROOT / name).is_file()), None)
    if library is None:
        raise SystemExit("Project library missing; run tools/configure_build.py first")

    command = [
        inet, "-u", "Cmdenv", "-n", f"../../src:{inet_root}/src", "-l", str(library),
        "-f", "omnetpp.ini", "-c", args.config, "-r", "0",
        f"--seed-set={args.seed_set}", "--cmdenv-express-mode=false",
        f"--output-scalar-file={sca}", f"--output-vector-file={vec}",
        f'--*.node[*].app[0].eventLog="{events}"',
    ]
    result = subprocess.run(command, cwd=ROOT / "simulations" / "mesh", capture_output=True, text=True)
    (run_dir / "stdout.log").write_text(result.stdout + result.stderr)
    manifest = {
        "config": args.config,
        "routing": "ML Decision Tree application-level next-hop forwarding",
        "status": "simulation_failed" if result.returncode else "simulated",
        "command": command,
        "seed_set": args.seed_set,
        "application_traffic": {"payload_bytes": 128, "send_interval_s": 0.2,
                                "start_time_s": 2.0, "stop_time_s": 58.0},
        "failure_time_s": failure_time,
        "restart_time_s": restart_time,
    }
    if result.returncode:
        manifest["return_code"] = result.returncode
    else:
        try:
            manifest["metrics"] = analyze(events, run_dir, failure_time=failure_time,
                                           restart_time=restart_time)
            manifest["status"] = "validated"
        except Exception as error:
            manifest["status"] = "trace_validation_failed"
            manifest["validation_error"] = str(error)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"{manifest['status']}: {run_dir}")
    if manifest.get("metrics"):
        metrics = manifest["metrics"]
        print(f"PDR={metrics['pdr']:.4f} delivered={metrics['packets_received_unique']}/{metrics['packets_generated']} "
              f"delay_ms={metrics['mean_delay_ms']} hops={metrics['mean_packet_hops']} "
              f"routes={metrics['valid_delivered_path_count']}")
    if result.returncode or manifest["status"] != "validated":
        print((run_dir / "stdout.log").read_text()[-4000:], file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
