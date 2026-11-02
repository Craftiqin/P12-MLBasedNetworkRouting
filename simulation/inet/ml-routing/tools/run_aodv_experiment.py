#!/usr/bin/env python3
"""Run isolated AODV demo/measurement and generate evidence dashboard."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = {
    "CleanVisualDemo": (2.0, 18.0),
    "Normal": (2.0, 58.0),
    "RelayFailure": (2.0, 58.0),
    "AODVPreferredPathFailure": (2.0, 58.0),
    "AODVLinkRecovery": (2.0, 58.0),
    "AODVDegradedReliability": (2.0, 58.0),
    "AODVIncreasedLatency": (2.0, 58.0),
}
FAILURE_TIMES = {"RelayFailure": 30.0, "PreferredPathFailure": 30.0,
                 "AODVPreferredPathFailure": 30.0, "LinkRecovery": 25.0,
                 "AODVLinkRecovery": 30.0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", choices=CONFIGS, default="CleanVisualDemo")
    parser.add_argument("--ui", choices=("Qtenv", "Cmdenv"), default="Qtenv")
    parser.add_argument("--run-number", type=int, default=0)
    parser.add_argument("--seed-set", type=int, default=17,
                        help="OMNeT++ random seed-set index for matched trials")
    parser.add_argument("--log-level", choices=("error", "warn", "info", "debug"), default="warn",
                        help="Cmdenv log threshold; --diagnostics enables trace")
    parser.add_argument("--diagnostics", action="store_true", help="also save OMNeT++ event log and enable TRACE in Cmdenv")
    args = parser.parse_args()

    inet = shutil.which("inet")
    inet_root = os.environ.get("INET_ROOT")
    if not inet or not inet_root:
        raise SystemExit("INET environment missing. Source OMNeT++ setenv and INET setenv first.")
    free = shutil.disk_usage(ROOT).free
    if free < 256 * 1024 * 1024:
        raise SystemExit(f"Need at least 256 MiB free for result files; found {free / 1024**2:.0f} MiB.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / "experiments" / "runs" / f"{stamp}-AODV-{args.config}"
    suffix = 1
    while run_dir.exists():
        run_dir = ROOT / "experiments" / "runs" / f"{stamp}-{suffix}-AODV-{args.config}"
        suffix += 1
    run_dir.mkdir(parents=True)
    pattern = str(run_dir / f"{args.config}-run{args.run_number}")
    scalar = pattern + ".sca"
    vector = pattern + ".vec"
    route = pattern + ".rt"
    eventlog = pattern + ".elog"
    log_level = "trace" if args.diagnostics and args.ui == "Cmdenv" else args.log_level
    command = [inet, "-u", args.ui, "-n", f"src:{inet_root}/src", "-f",
               "simulations/mesh/omnetpp.ini", "-c", args.config, "-r", str(args.run_number),
               f"--seed-set={args.seed_set}",
               f"--output-scalar-file={scalar}", f"--output-vector-file={vector}",
               f'--*.routingTableRecorder.logfile="{route}"', f"--**.cmdenv-log-level={log_level}"]
    if args.diagnostics:
        command.extend(["--record-eventlog=true", f"--eventlog-file={eventlog}"])

    manifest = {"routing": "INET AODV", "config": args.config, "ui": args.ui,
                "run_number": args.run_number, "seed_set": args.seed_set,
                "failure_time_s": FAILURE_TIMES.get(args.config),
                "restart_time_s": 45.0 if args.config == "AODVLinkRecovery" else
                                  40.0 if args.config == "LinkRecovery" else None,
                "application_traffic": {"payload_bytes": 128, "send_interval_s": 0.2,
                                        "start_time_s": 2.0, "stop_time_s": 18.0 if args.config == "CleanVisualDemo" else 58.0},
                "observation_window_s": list(CONFIGS[args.config]),
                "diagnostics_eventlog": args.diagnostics, "command": command,
                "free_disk_bytes_before_run": free}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Experiment output: {run_dir}", flush=True)
    print(f"Free disk before run: {free / 1024**3:.2f} GiB", flush=True)
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode:
        raise SystemExit(f"OMNeT++ exited with status {result.returncode}; inspect {run_dir / 'manifest.json'} and simulation output.")

    sca_path = run_dir / f"{args.config}-run{args.run_number}.sca"
    vec_path = run_dir / f"{args.config}-run{args.run_number}.vec"
    rt_path = run_dir / f"{args.config}-run{args.run_number}.rt"
    missing = [str(path) for path in (sca_path, vec_path) if not path.exists()]
    if missing:
        raise SystemExit("Simulation completed but expected evidence files are missing: " + ", ".join(missing))
    start, end = CONFIGS[args.config]
    dashboard = ROOT / "tools" / "build_dashboard.py"
    subprocess.run([sys.executable, str(dashboard), str(sca_path), str(vec_path), str(rt_path),
                    "--output", str(run_dir / "dashboard"), "--observation-start", str(start),
                    "--observation-end", str(end), "--inifile", "simulations/mesh/omnetpp.ini"],
                   cwd=ROOT, check=True)
    print(f"Raw result files and manifest: {run_dir}")


if __name__ == "__main__":
    main()
