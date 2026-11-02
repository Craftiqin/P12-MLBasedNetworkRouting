#!/usr/bin/env python3
"""Export OMNeT++ .sca scalar/statistic records to a small CSV summary."""

import argparse
import csv
import re
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
    found = [v for k, v in values.items() if path_prefix in k and k.endswith(name_suffix)]
    return found[0] if found else None


def route_metrics(path: Path, observation_seconds: float) -> tuple[float | None, int | None, float | None]:
    rt_path = path.with_suffix(".rt")
    if not rt_path.exists():
        return None, None, None
    events = []
    for raw in rt_path.read_text(errors="replace").splitlines():
        parts = raw.split()
        if len(parts) < 7 or parts[0] not in ("+R", "-R", "*R") or parts[5] != "10.0.0.1/32":
            continue
        try:
            time_s = float(parts[2].removesuffix("s"))
        except ValueError:
            continue
        events.append((time_s, parts[0], parts[4], parts[6]))
    events.sort()
    routes: dict[str, str] = {}
    snapshots = []
    source_next = None
    switches = 0
    switch_times = []
    for time_s, action, own_ip, next_hop in events:
        if action == "-R":
            if routes.get(own_ip) == next_hop:
                routes.pop(own_ip, None)
        else:
            routes[own_ip] = next_hop
        if own_ip == "10.0.0.6" and action != "-R":
            if source_next is not None and source_next != next_hop:
                switches += 1
                switch_times.append(time_s)
            source_next = next_hop
        snapshots.append((time_s, dict(routes)))

    def hops_to_gateway(table: dict[str, str]) -> int | None:
        current = "10.0.0.6"
        hops = 0
        visited = set()
        while current != "10.0.0.1" and current in table and current not in visited and hops <= 8:
            visited.add(current)
            current = table[current]
            hops += 1
        return hops if current == "10.0.0.1" else None

    # Sample routes at each configured source packet time; routes are INET
    # forwarding-table evidence, not packet-header hop measurements.
    sample_hops = []
    snap_index = -1
    active = {}
    for i in range(int(observation_seconds / 0.2)):
        send_time = 2.0 + i * 0.2
        while snap_index + 1 < len(snapshots) and snapshots[snap_index + 1][0] <= send_time:
            snap_index += 1
            active = snapshots[snap_index][1]
        hops = hops_to_gateway(active)
        if hops is not None:
            sample_hops.append(hops)
    mean_hops = sum(sample_hops) / len(sample_hops) if sample_hops else None

    recovery_s = None
    if path.stem.startswith("RelayFailure"):
        crash_time = 30.0
        after = [t for t in switch_times if t >= crash_time]
        if after:
            recovery_s = after[0] - crash_time
    return mean_hops, switches, recovery_s


def summarize(path: Path, payload_bytes: int, observation_seconds: float) -> dict:
    scalars, stats, config = read_sca(path)
    sent = find_value(scalars, "node[5].app[0].", "packetSent:count")
    received = find_value(scalars, "node[0].app[0].", "packetReceived:count")
    rx_bytes = find_value(scalars, "node[0].app[0].", "packetReceived:sum(packetBytes)")
    delay_blocks = [fields for key, fields in stats.items()
                    if "node[0].app[0]." in key and ".endToEndDelay" in key]
    avg_delay_s = delay_blocks[0].get("mean") if delay_blocks else None
    pdr = received / sent if sent not in (None, 0) and received is not None else None
    bits = rx_bytes * 8 if rx_bytes is not None else received * payload_bytes * 8 if received is not None else None
    throughput_bps = bits / observation_seconds if bits is not None else None
    hops, route_switches, recovery = route_metrics(path, observation_seconds)
    return {"config":config,"result_file":path.name,"packets_sent":sent,"packets_received":received,
            "pdr":pdr,"packet_loss_ratio":1-pdr if pdr is not None else None,
            "mean_end_to_end_delay_s":avg_delay_s,"throughput_bps":throughput_bps,
            "mean_route_hop_count":hops,"source_route_changes":route_switches,
            "route_recovery_time_s":recovery}


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
