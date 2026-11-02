#!/usr/bin/env python3
"""Export OMNeT++ .sca scalar/statistic records to a small CSV summary."""

import argparse
import csv
from pathlib import Path


def read_sca(path: Path) -> tuple[dict[str, float], dict[str, dict[str, float]], str]:
    scalars: dict[str, float] = {}
    stats: dict[str, dict[str, float]] = {}
    config = "unknown"
    current = None
    for raw in path.read_text(errors="replace").splitlines():
        parts = raw.split()
        if not parts:
            continue
        if parts[0] == "attr" and len(parts) >= 3 and parts[1] == "configname":
            config = parts[2].strip('"')
        elif parts[0] == "scalar" and len(parts) >= 4:
            try:
                scalars[f"{parts[1]}.{parts[2]}"] = float(parts[3])
            except ValueError:
                pass
            current = None
        elif parts[0] == "statistic" and len(parts) >= 3:
            current = f"{parts[1]}.{parts[2]}"
            stats[current] = {}
        elif parts[0] == "field" and current and len(parts) >= 3:
            try:
                stats[current][parts[1]] = float(parts[2])
            except ValueError:
                pass
        elif parts[0] in ("bin", "end"):
            current = None
    return scalars, stats, config


def find_value(values: dict[str, float], path_prefix: str, name_suffix: str) -> float | None:
    found = [v for k, v in values.items() if k.startswith(path_prefix) and k.endswith(name_suffix)]
    return found[0] if found else None


def summarize(path: Path, payload_bytes: int, observation_seconds: float) -> dict:
    scalars, stats, config = read_sca(path)
    sent = find_value(scalars, "node[5].app[0].", "packetSent:count")
    received = find_value(scalars, "node[0].app[0].", "packetReceived:count")
    rx_bytes = find_value(scalars, "node[0].app[0].", "packetReceived:sum(packetBytes)")
    delay_blocks = [fields for key, fields in stats.items()
                    if key.startswith("node[0].app[0].") and key.endswith(".endToEndDelay")]
    avg_delay_s = delay_blocks[0].get("mean") if delay_blocks else None
    pdr = received / sent if sent not in (None, 0) and received is not None else None
    bits = rx_bytes * 8 if rx_bytes is not None else received * payload_bytes * 8 if received is not None else None
    throughput_bps = bits / observation_seconds if bits is not None else None
    return {"config":config,"result_file":path.name,"packets_sent":sent,"packets_received":received,
            "pdr":pdr,"packet_loss_ratio":1-pdr if pdr is not None else None,
            "mean_end_to_end_delay_s":avg_delay_s,"throughput_bps":throughput_bps,
            "hop_count":"not exported by stock UDP sink",
            "route_switch_count":"inspect companion .rt routing log",
            "recovery_time":"inspect delivery sequence and .rt routing log"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results_dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/omnet_summary.csv"))
    parser.add_argument("--payload-bytes", type=int, default=128)
    parser.add_argument("--observation-seconds", type=float, default=56.0)
    args = parser.parse_args()
    rows = [summarize(p,args.payload_bytes,args.observation_seconds)
            for p in sorted(args.results_dir.glob("*.sca"))]
    if not rows:
        raise SystemExit(f"No .sca scalar files found in {args.results_dir}")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(f"Exported {len(rows)} run summaries to {args.output}")


if __name__ == "__main__":
    main()
