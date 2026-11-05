#!/usr/bin/env python3
"""Run one Decision Tree configuration into a unique, validated results folder."""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.analyze_runtime_trace import analyze  # noqa: E402
from tools.simulation_process import launch_interactive_simulation, run_finite_simulation  # noqa: E402

CONFIGS = {"MLRouting", "MLRoutePreference", "MLPreferredPathFailure", "MLNoRoute", "MLLinkRecovery",
           "MLDegradedReliability", "MLIncreasedLatency", "MLVisualDemo"}
DEFAULT_TIMEOUT_SECONDS = 60


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", choices=sorted(CONFIGS), default="MLRouting")
    parser.add_argument("--ui", choices=("Cmdenv", "Qtenv"), default="Cmdenv",
                        help="Cmdenv is finite batch mode; Qtenv launches interactively and returns")
    parser.add_argument("--seed-set", type=int, default=17)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS,
                        help="wall-clock limit for finite Cmdenv simulation (default: 60)")
    args = parser.parse_args()
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
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

    ned_path = os.pathsep.join((str(ROOT / "src"), str(Path(inet_root) / "src")))
    command = [
        inet, "-u", args.ui, "-n", ned_path, "-l", str(library),
        "-f", "omnetpp.ini", "-c", args.config, "-r", "0",
        f"--seed-set={args.seed_set}", "--cmdenv-express-mode=false",
        f"--output-scalar-file={sca}", f"--output-vector-file={vec}",
        f'--*.node[*].app[0].eventLog="{events}"',
    ]
    if args.ui == "Qtenv":
        log_path = run_dir / "qtenv.log"
        try:
            pid = launch_interactive_simulation(command, ROOT / "simulations" / "mesh", log_path)
        except OSError as error:
            (run_dir / "runner-error.txt").write_text(f"Could not start Qtenv: {error}\nCommand: {command!r}\n")
            raise SystemExit(f"Runner failed to start Qtenv; details: {run_dir}") from error
        manifest = {
            "config": args.config,
            "routing": "ML Decision Tree application-level next-hop forwarding",
            "ui": "Qtenv",
            "status": "interactive_started",
            "command": command,
            "pid": pid,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "log": str(log_path),
            "sim_time_limit_s": 16 if args.config == "MLVisualDemo" else 60,
            "note": "Interactive session returned to caller; run simulation in Qtenv, then close GUI to exit.",
            "seed_set": args.seed_set,
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Qtenv launched (interactive; PID {pid}): {run_dir}", flush=True)
        print(f"Qtenv log: {log_path}", flush=True)
        return

    try:
        result = run_finite_simulation(command, ROOT / "simulations" / "mesh", args.timeout_seconds)
    except OSError as error:
        (run_dir / "runner-error.txt").write_text(f"Could not start simulator: {error}\nCommand: {command!r}\n")
        raise SystemExit(f"Runner failed to start simulator; details: {run_dir / 'runner-error.txt'}") from error
    (run_dir / "stdout.log").write_text(result.stdout)
    (run_dir / "stderr.log").write_text(result.stderr)
    if result.timed_out:
        status = "simulator_timeout"
    elif result.returncode:
        status = "simulator_failed"
    else:
        status = "simulated"
    manifest = {
        "config": args.config,
        "routing": "ML Decision Tree application-level next-hop forwarding",
        "ui": "Cmdenv",
        "status": status,
        "command": command,
        "timeout_seconds": args.timeout_seconds,
        "started_at_utc": result.started_at_utc,
        "ended_at_utc": result.ended_at_utc,
        "elapsed_seconds": result.elapsed_seconds,
        "return_code": result.returncode,
        "seed_set": args.seed_set,
        "application_traffic": {"payload_bytes": 128,
                                "send_interval_s": 0.5 if args.config == "MLVisualDemo" else 0.2,
                                "start_time_s": 2.0,
                                "stop_time_s": 14.0 if args.config == "MLVisualDemo" else 58.0},
        "failure_time_s": failure_time,
        "restart_time_s": restart_time,
    }
    if result.timed_out:
        manifest["timeout_diagnostics"] = (
            f"Simulator exceeded {args.timeout_seconds:g}s wall-clock timeout; "
            "sent SIGTERM, then SIGKILL only if it did not exit within 5s. "
            f"Command: {command!r}"
        )
    if not result.timed_out and result.returncode == 0:
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
    if result.timed_out or result.returncode or manifest["status"] != "validated":
        print(f"elapsed={result.elapsed_seconds:.3f}s return_code={result.returncode} "
              f"timed_out={result.timed_out} command={command!r}", file=sys.stderr)
        print((run_dir / "stdout.log").read_text()[-3000:], file=sys.stderr)
        print((run_dir / "stderr.log").read_text()[-1000:], file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
