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
sys.path.insert(0, str(ROOT))
from tools.simulation_process import launch_interactive_simulation, run_finite_simulation  # noqa: E402

DEFAULT_TIMEOUT_SECONDS = 60
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
    parser.add_argument("--ui", choices=("Qtenv", "Cmdenv"), default="Cmdenv",
                        help="Cmdenv runs finite batch jobs; Qtenv launches interactively and returns")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS,
                        help="wall-clock limit for Cmdenv only (default: 60)")
    parser.add_argument("--run-number", type=int, default=0)
    parser.add_argument("--seed-set", type=int, default=17,
                        help="OMNeT++ random seed-set index for matched trials")
    parser.add_argument("--log-level", choices=("error", "warn", "info", "debug"), default="warn",
                        help="Cmdenv log threshold; --diagnostics enables trace")
    parser.add_argument("--diagnostics", action="store_true", help="also save OMNeT++ event log and enable TRACE in Cmdenv")
    args = parser.parse_args()
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")

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
    ned_path = os.pathsep.join((str(ROOT / "src"), str(Path(inet_root) / "src")))
    command = [inet, "-u", args.ui, "-n", ned_path, "-f",
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
                "timeout_seconds": args.timeout_seconds if args.ui == "Cmdenv" else None,
                "free_disk_bytes_before_run": free}
    if args.ui == "Qtenv":
        log_path = run_dir / "qtenv.log"
        try:
            pid = launch_interactive_simulation(command, ROOT, log_path)
        except OSError as error:
            manifest.update(status="runner_failed", runner_error=str(error))
            (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            raise SystemExit(f"Runner could not launch Qtenv: {error}; details: {run_dir}") from error
        manifest.update(status="interactive_started", pid=pid,
                        started_at_utc=datetime.now(timezone.utc).isoformat(), log=str(log_path),
                        note="Qtenv stays open for inspection after sim-time-limit; close GUI to exit.")
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Qtenv launched (interactive; PID {pid}): {run_dir}", flush=True)
        print(f"Qtenv log: {log_path}", flush=True)
        return

    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Experiment output: {run_dir}", flush=True)
    print(f"Free disk before run: {free / 1024**3:.2f} GiB", flush=True)
    try:
        result = run_finite_simulation(command, ROOT, args.timeout_seconds)
    except OSError as error:
        manifest.update(status="runner_failed", runner_error=str(error))
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        raise SystemExit(f"Runner could not start OMNeT++: {error}; details: {run_dir}") from error
    (run_dir / "stdout.log").write_text(result.stdout)
    (run_dir / "stderr.log").write_text(result.stderr)
    manifest.update(started_at_utc=result.started_at_utc, ended_at_utc=result.ended_at_utc,
                    elapsed_seconds=result.elapsed_seconds, return_code=result.returncode,
                    status="simulator_timeout" if result.timed_out else
                           "simulator_failed" if result.returncode else "simulated")
    if result.timed_out:
        manifest["timeout_diagnostics"] = (
            f"Exceeded {args.timeout_seconds:g}s; sent SIGTERM then SIGKILL after 5s grace. "
            f"Command: {command!r}"
        )
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if result.timed_out or result.returncode:
        raise SystemExit(f"OMNeT++ failure: timed_out={result.timed_out}, return_code={result.returncode}, "
                         f"elapsed={result.elapsed_seconds:.3f}s, command={command!r}; outputs: {run_dir}")

    sca_path = run_dir / f"{args.config}-run{args.run_number}.sca"
    vec_path = run_dir / f"{args.config}-run{args.run_number}.vec"
    rt_path = run_dir / f"{args.config}-run{args.run_number}.rt"
    missing = [str(path) for path in (sca_path, vec_path) if not path.exists()]
    if missing:
        manifest.update(status="output_collection_failed", missing_outputs=missing)
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        raise SystemExit("Simulation completed but expected evidence files are missing: " + ", ".join(missing))
    start, end = CONFIGS[args.config]
    dashboard = ROOT / "tools" / "build_dashboard.py"
    try:
        subprocess.run([sys.executable, str(dashboard), str(sca_path), str(vec_path), str(rt_path),
                        "--output", str(run_dir / "dashboard"), "--observation-start", str(start),
                        "--observation-end", str(end), "--inifile", "simulations/mesh/omnetpp.ini"],
                       cwd=ROOT, check=True, timeout=30)
    except subprocess.TimeoutExpired as error:
        manifest.update(status="postprocessing_timeout", postprocess_timeout_seconds=30)
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        raise SystemExit(f"Dashboard timeout after 30s; simulation elapsed="
                         f"{result.elapsed_seconds:.3f}s; outputs: {run_dir}") from error
    except subprocess.CalledProcessError as error:
        manifest.update(status="postprocessing_failed", postprocess_return_code=error.returncode)
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        raise SystemExit(f"Dashboard failed ({error.returncode}); simulation itself exited successfully "
                         f"after {result.elapsed_seconds:.3f}s; outputs: {run_dir}") from error
    manifest.update(status="validated", expected_outputs=[str(sca_path), str(vec_path), str(run_dir / "dashboard" / "index.html")])
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Raw result files and manifest: {run_dir}")


if __name__ == "__main__":
    main()
