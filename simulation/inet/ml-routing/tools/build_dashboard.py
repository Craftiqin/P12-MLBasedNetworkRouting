#!/usr/bin/env python3
"""Build auditable CSV and dependency-free SVG/HTML views from one OMNeT++ run."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
from pathlib import Path


def read_scalars(path: Path) -> tuple[dict[str, float], dict[str, dict[str, float]], dict[str, str]]:
    scalars: dict[str, float] = {}
    stats: dict[str, dict[str, float]] = {}
    attrs: dict[str, str] = {}
    current = None
    for raw in path.read_text(errors="replace").splitlines():
        parts = raw.split(maxsplit=3)
        if not parts:
            continue
        if parts[0] == "attr" and len(parts) >= 3:
            attrs[parts[1]] = parts[2].strip('"')
        elif parts[0] == "config" and len(parts) >= 3:
            attrs[f"config:{parts[1]}"] = parts[2].strip('"')
        elif parts[0] == "scalar" and len(parts) >= 4:
            try:
                scalars[f"{parts[1]}.{parts[2]}"] = float(parts[3])
            except ValueError:
                continue
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
    return scalars, stats, attrs


def read_vectors(path: Path) -> dict[str, list[tuple[float, float]]]:
    definitions: dict[int, str] = {}
    vectors: dict[str, list[tuple[float, float]]] = {}
    for raw in path.read_text(errors="replace").splitlines():
        parts = raw.split()
        if not parts:
            continue
        if parts[0] == "vector" and len(parts) >= 4:
            vector_id = int(parts[1])
            definitions[vector_id] = f"{parts[2]} {parts[3]}"
            vectors.setdefault(definitions[vector_id], [])
            continue
        # OMNeT++ vector format v3: vector ID, event number, sim time, value.
        # Also accept compact id/time/value rows for small test fixtures.
        try:
            if len(parts) == 4:
                vector_id, time_s, value = int(parts[0]), float(parts[2]), float(parts[3])
            elif len(parts) == 3:
                vector_id, time_s, value = int(parts[0]), float(parts[1]), float(parts[2])
            else:
                continue
        except ValueError:
            continue
        key = definitions.get(vector_id)
        if key is not None:
            vectors[key].append((time_s, value))
    return vectors


def _records(vectors: dict[str, list[tuple[float, float]]], node: int, stat: str) -> list[tuple[float, float]]:
    marker = f"node[{node}].app[0] {stat}"
    return next((values for key, values in vectors.items() if marker in key), [])


def read_route_changes(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events = []
    active_next_hop = None
    for raw in path.read_text(errors="replace").splitlines():
        parts = raw.split()
        if len(parts) < 7 or parts[0] not in ("+R", "-R", "*R"):
            continue
        if "node[5]" not in parts[3] or parts[5] != "10.0.0.1/32":
            continue
        try:
            time_s = float(parts[2].removesuffix("s"))
        except ValueError:
            continue
        next_hop = parts[6]
        previous_next_hop = active_next_hop
        if parts[0] == "-R":
            if active_next_hop == next_hop:
                active_next_hop = None
        else:
            active_next_hop = next_hop
        events.append({"time_s": time_s, "action": parts[0], "next_hop": next_hop,
                       "active_next_hop": active_next_hop,
                       "changed": previous_next_hop is not None and previous_next_hop != active_next_hop})
    return events


def build_packet_rows(vec: dict[str, list[tuple[float, float]]]) -> tuple[list[dict], dict]:
    generated = _records(vec, 5, "packetSent:vector(packetBytes)")
    received_times = _records(vec, 0, "packetReceived:vector(packetBytes)")
    sequence_records = _records(vec, 0, "rcvdPkSeqNo:vector")
    delay_records = _records(vec, 0, "endToEndDelay:vector")
    if not (len(received_times) == len(sequence_records) == len(delay_records)):
        raise ValueError("Gateway packetReceived, sequence-number, and delay vectors differ; refusing ambiguous packet joins")

    # INET 4.7 UdpBasicApp sets ApplicationPacket.sequenceNumber=numSent; it
    # begins at zero. This maps emitted app packets to stable source IDs.
    sent = [{"packet_id": int(sequence), "source": "node[5]", "destination": "node[0]",
             "generated_s": time_s} for sequence, (time_s, _size) in enumerate(generated)]
    generated_ids = {packet["packet_id"] for packet in sent}

    received_by_id: dict[int, dict] = {}
    duplicate_ids = []
    for index, (received_s, seq_value) in enumerate(sequence_records):
        packet_id = int(seq_value)
        record = {"received_s": received_times[index][0] if index < len(received_times) else received_s,
                  "delay_s": delay_records[index][1] if index < len(delay_records) else None}
        if packet_id in received_by_id:
            duplicate_ids.append(packet_id)
        else:
            received_by_id[packet_id] = record
    unexpected_ids = sorted(set(received_by_id) - generated_ids)
    if unexpected_ids:
        raise ValueError(f"Gateway received sequence IDs absent from source trace: {unexpected_ids[:8]}")

    rows = []
    for packet in sent:
        rx = received_by_id.get(packet["packet_id"])
        rows.append({**packet,
                     "received_s": rx["received_s"] if rx else None,
                     "delay_s": rx["delay_s"] if rx else None,
                     "delivery_status": "delivered" if rx else "not_received_by_end",
                     "hop_count": None,
                     "drop_reason": "" if rx else "No destination receive event; drop location/reason not measured"})
    details = {"generated_count": len(sent), "received_event_count": len(sequence_records),
               "unique_received_count": len(received_by_id), "duplicate_received_ids": duplicate_ids,
               "sequence_vector_count": len(sequence_records), "packet_received_vector_count": len(received_times),
               "delay_vector_count": len(delay_records)}
    return rows, details


def _xml_failure_time(config: str, inifile: Path) -> float | None:
    scenario_by_config = {"RelayFailure": "relay_failure.xml",
                          "PreferredPathFailure": "preferred_path_failure.xml",
                          "AODVPreferredPathFailure": "ml_path_failure.xml",
                          "LinkRecovery": "link_recovery.xml",
                          "AODVLinkRecovery": "ml_link_recovery.xml"}
    name = scenario_by_config.get(config)
    if not name:
        return None
    scenario = inifile.parent / "scenarios" / name
    match = re.search(r'\bt="([0-9.]+)s"', scenario.read_text(errors="replace")) if scenario.exists() else None
    return float(match.group(1)) if match else None


def _svg(title: str, content: str, width: int = 760, height: int = 360) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="{html.escape(title)}"><rect width="100%" height="100%" fill="#fff"/>'
            f'<text x="32" y="32" font-size="20" font-family="sans-serif" font-weight="600">{html.escape(title)}</text>'
            f'{content}</svg>')


def _bar_svg(title: str, label: str, value: float | None, maximum: float, suffix: str, note: str = "") -> str:
    if value is None:
        body = '<text x="380" y="190" text-anchor="middle" fill="#596579" font-size="22">Not measured</text>'
    else:
        width = max(0.0, min(620.0, 620.0 * value / maximum))
        body = (f'<text x="40" y="125" font-size="15">{html.escape(label)}</text>'
                f'<rect x="40" y="145" width="620" height="36" rx="5" fill="#e7edf4"/>'
                f'<rect x="40" y="145" width="{width:.1f}" height="36" rx="5" fill="#176b55"/>'
                f'<path d="M40 188 H660" stroke="#657287"/>'
                f'<text x="40" y="208" font-size="12">0</text>'
                f'<text x="660" y="208" text-anchor="end" font-size="12">{maximum:g}{html.escape(suffix)}</text>'
                f'<text x="40" y="245" font-size="20" font-weight="600">{value:.3f}{html.escape(suffix)}</text>')
    if note:
        body += f'<text x="40" y="290" font-size="14" fill="#596579">{html.escape(note)}</text>'
    return _svg(title, body)


def _delay_svg(delays: list[float]) -> str:
    title = "End-to-end delay per delivered packet (ms)"
    if not delays:
        return _svg(title, '<text x="380" y="190" text-anchor="middle">Not measured</text>')
    bins = 12
    maximum = max(delays) * 1.05 or 1
    counts = [0] * bins
    for delay in delays:
        counts[min(bins - 1, int(delay / maximum * bins))] += 1
    height = max(counts) or 1
    bars = []
    for i, count in enumerate(counts):
        x = 60 + i * 55
        h = count / height * 200
        bars.append(f'<rect x="{x}" y="{285-h:.1f}" width="38" height="{h:.1f}" fill="#2874a6"/>')
    mean_ms = sum(delays) / len(delays) * 1000
    sd_ms = math.sqrt(sum((x - mean_ms / 1000) ** 2 for x in delays) / len(delays)) * 1000
    body = ''.join(bars) + f'<text x="60" y="320" font-size="13">0</text><text x="650" y="320" font-size="13">{maximum*1000:.2f} ms</text>'
    body += '<text x="18" y="190" font-size="13" transform="rotate(-90 18 190)">Delivered packets (count)</text>'
    body += '<text x="330" y="342" font-size="13">End-to-end delay (ms)</text>'
    body += f'<text x="60" y="375" font-size="14">n={len(delays)}; mean={mean_ms:.3f} ms; within-run SD={sd_ms:.3f} ms</text>'
    return _svg(title, body, height=400)


def _timeline_svg(rows: list[dict], sim_end: float) -> str:
    title = "Application packets over simulation time"
    if not rows:
        return _svg(title, '<text x="380" y="190" text-anchor="middle">No packet records</text>')
    generated = sorted(r["generated_s"] for r in rows)
    delivered = sorted(r["received_s"] for r in rows if r["received_s"] is not None)
    xmax = max(sim_end, max(generated), max(delivered, default=0), 1)
    ymax = len(rows) or 1
    body = '<path d="M70 290 H700 M70 60 V290" stroke="#657287" fill="none"/>'
    for values, color in ((generated, "#2874a6"), (delivered, "#176b55")):
        points = [(70 + (t / xmax) * 630, 290 - ((i + 1) / ymax) * 210) for i, t in enumerate(values)]
        if points:
            d = f'M70 {290 - 1/ymax*210:.2f} ' + ' '.join(f'L{x:.2f} {y:.2f}' for x, y in points)
            body += f'<path d="{d}" stroke="{color}" stroke-width="3" fill="none"/>'
    body += '<text x="75" y="45" fill="#2874a6">Generated</text><text x="180" y="45" fill="#176b55">Delivered at gateway</text>'
    body += '<text x="18" y="180" font-size="13" transform="rotate(-90 18 180)">Cumulative packets (count)</text>'
    body += f'<text x="330" y="340" font-size="14">Simulation time (s), 0 to {xmax:.1f}</text>'
    body += f'<text x="75" y="315" font-size="13">{len(rows)} generated; {len(delivered)} unique delivered; {len(rows)-len(delivered)} not received by end</text>'
    return _svg(title, body)


def _route_svg(events: list[dict], failure_time: float | None, rows: list[dict], sim_end: float) -> str:
    title = "AODV route and failure timeline"
    if not events and failure_time is None:
        return _svg(title, '<text x="380" y="190" text-anchor="middle">No failure or route-change events in this run</text>')
    times = [e["time_s"] for e in events] + ([failure_time] if failure_time is not None else [])
    xmax = max(times + [sim_end, 1])
    body = '<path d="M70 260 H700" stroke="#657287"/>'
    if failure_time is not None:
        x = 70 + failure_time / xmax * 630
        body += f'<path d="M{x:.1f} 70 V270" stroke="#b42318" stroke-width="2" stroke-dasharray="6 5"/><text x="{x+4:.1f}" y="65" fill="#b42318">relay failure {failure_time:g}s</text>'
    source_hops = [e for e in events if e["action"] != "-R"]
    for i, event in enumerate(source_hops):
        x = 70 + event["time_s"] / xmax * 630
        label = "changed" if event["changed"] else "installed"
        body += f'<circle cx="{x:.1f}" cy="155" r="8" fill="#176b55"/><text x="{x+8:.1f}" y="145" font-size="12">{label}: next hop {html.escape(event["next_hop"])} @ {event["time_s"]:.3f}s</text>'
    if failure_time is not None:
        after = [r["received_s"] for r in rows if r["received_s"] is not None and r["received_s"] >= failure_time]
        if after:
            recovered = min(after)
            x = 70 + recovered / xmax * 630
            body += f'<path d="M{x:.1f} 210 l9 16 h-18 z" fill="#2874a6"/><text x="{x+10:.1f}" y="232" font-size="12">first post-failure delivery {recovered:.3f}s; interval {recovered-failure_time:.3f}s</text>'
        else:
            body += '<text x="75" y="220" fill="#b42318">No post-failure delivery observed</text>'
    body += f'<text x="340" y="310" font-size="14">Simulation time (s), 0 to {xmax:.1f}</text>'
    return _svg(title, body)


def generate(sca_path: Path, vec_path: Path, rt_path: Path, output_dir: Path,
             observation_start: float, observation_end: float, inifile: Path) -> dict:
    scalars, stats, attrs = read_scalars(sca_path)
    vectors = read_vectors(vec_path)
    rows, trace_counts = build_packet_rows(vectors)
    if not rows:
        raise ValueError("No source packetSent vector found; cannot establish application packet population")
    if observation_end <= observation_start:
        raise ValueError("Observation end must be after observation start")
    delivered = [row for row in rows if row["delivery_status"] == "delivered"]
    delays = [row["delay_s"] for row in delivered if row["delay_s"] is not None]
    sent_count = len(rows)
    received_count = len({row["packet_id"] for row in delivered})
    pdr = received_count / sent_count if sent_count else None
    rx_bytes = next((value for key, value in scalars.items()
                     if "node[0].app[0].packetReceived:sum(packetBytes)" in key), None)
    bytes_source = "UdpSink packetReceived:sum(packetBytes) scalar" if rx_bytes is not None else "Not measured: byte scalar absent"
    throughput = rx_bytes * 8 / (observation_end - observation_start) if rx_bytes is not None else None
    mean_delay = sum(delays) / len(delays) if delays else None
    sd_delay = math.sqrt(sum((d - mean_delay) ** 2 for d in delays) / len(delays)) if delays else None
    routes = read_route_changes(rt_path)
    failure_time = _xml_failure_time(attrs.get("configname", ""), inifile)
    time_limit = attrs.get("config:sim-time-limit", "")
    limit_match = re.fullmatch(r"([0-9.]+)(s|ms|us|ns)", time_limit)
    scale = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "ns": 1e-9}
    sim_end = float(limit_match.group(1)) * scale[limit_match.group(2)] if limit_match else max(
        [t for t, _ in _records(vectors, 5, "packetSent:vector(packetBytes)")] + [observation_end])
    first_post_failure_delivery = min((r["received_s"] for r in delivered
                                       if failure_time is not None and r["received_s"] is not None
                                       and r["received_s"] >= failure_time), default=None)
    recovery_time = first_post_failure_delivery - failure_time if first_post_failure_delivery is not None else None
    summary = {
        "routing": "INET AODV",
        "config": attrs.get("configname", "unknown"),
        "result_file": sca_path.name,
        "seed_set": attrs.get("seedset", "unknown"),
        "generated_unique_application_packets": sent_count,
        "received_unique_application_packets": received_count,
        "not_received_by_end": sent_count - received_count,
        "duplicate_receive_events": len(trace_counts["duplicate_received_ids"]),
        "packet_delivery_ratio": pdr,
        "not_delivered_ratio_by_end": 1 - pdr if pdr is not None else None,
        "mean_end_to_end_delay_s": mean_delay,
        "within_run_delay_sd_s": sd_delay,
        "throughput_bps": throughput,
        "throughput_byte_source": bytes_source,
        "packet_level_hop_count": "Not measured",
        "routing_control_overhead": "Not measured",
        "route_change_events": sum(1 for e in routes if e["changed"]),
        "failure_time_s": failure_time,
        "first_post_failure_delivery_s": first_post_failure_delivery,
        "route_recovery_time_s": recovery_time,
        "route_recovery_definition": "configured relay crash to first unique gateway delivery at or after crash time",
        "route_changes": routes,
        "ml_routing": "Pending; this run uses INET AODV",
        "trace_vector_counts": trace_counts,
        "observation_window_s": [observation_start, observation_end],
        "simulation_end_s": sim_end,
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    packet_csv = output_dir / "packet_outcomes.csv"
    fields = ["packet_id", "source", "destination", "generated_s", "received_s", "delay_s",
              "delivery_status", "hop_count", "drop_reason"]
    with packet_csv.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    config = summary["config"]
    charts = {
        "01-pdr.svg": _bar_svg("Packet delivery ratio", "AODV", pdr, 1.0, "%" if False else "", "ML comparison pending; packet population = unique UdpBasicApp sequence IDs"),
        "02-delay.svg": _delay_svg(delays),
        "03-throughput.svg": _bar_svg("Application throughput at gateway", "AODV", throughput, max(throughput or 0, 1) * 1.2, " bps", "Received application payload / configured traffic observation window"),
        "04-hop-count.svg": _bar_svg("Actual packet-level hop count", "", None, 1, "", "No per-packet hop trace is recorded by current AODV configuration"),
        "05-route-recovery.svg": _route_svg(routes, failure_time, rows, sim_end),
        "06-delivery-timeline.svg": _timeline_svg(rows, sim_end),
    }
    # PDR is displayed as percent, while JSON retains a [0,1] ratio.
    charts["01-pdr.svg"] = _bar_svg("Packet delivery ratio", "AODV", pdr * 100 if pdr is not None else None, 100, "%", "ML comparison pending; unique application IDs only")
    for name, content in charts.items():
        (output_dir / name).write_text(content + "\n")
    cards = [("Routing", "INET AODV"), ("PDR", f"{pdr*100:.2f}%" if pdr is not None else "Not measured"),
             ("Packets", f"{received_count}/{sent_count} unique delivered"),
             ("Mean delay", f"{mean_delay*1000:.3f} ms" if mean_delay is not None else "Not measured"),
             ("Throughput", f"{throughput:.1f} bit/s" if throughput is not None else "Not measured"), ("Packet hops", "Not measured"),
             ("Control overhead", "Not measured"), ("ML", "Pending")]
    card_html = "".join(f'<div class="card"><small>{html.escape(k)}</small><strong>{html.escape(v)}</strong></div>' for k, v in cards)
    figures = "".join(f'<figure><img src="{name}" alt="{html.escape(name)}"><figcaption>{html.escape(name[3:-4].replace("-", " ").title())}</figcaption></figure>' for name in charts)
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>AODV run dashboard</title>
<style>body{{font:16px system-ui,sans-serif;background:#f5f7fa;color:#182230;margin:2rem auto;max-width:1100px;padding:0 1rem}}h1{{margin-bottom:.2rem}}.sub{{color:#596579}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px;margin:24px 0}}.card,figure{{background:white;border:1px solid #dce3eb;border-radius:10px;padding:14px}}.card small,.card strong{{display:block}}.card strong{{font-size:1.15rem;margin-top:8px}}.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:16px}}figure{{margin:0}}img{{width:100%;height:auto}}figcaption{{font-size:.85rem;color:#596579}}.note{{background:#fff8e6;border-left:4px solid #d79b00;padding:12px}}</style>
<h1>{html.escape(config)} — AODV run</h1><p class="sub">Actual INET scalar, vector, and route-table records. Run file: {html.escape(sca_path.name)}. Seed set: {html.escape(str(summary['seed_set']))}.</p>
<div class="cards">{card_html}</div><p class="note">Only AODV measured. ML comparison pending. Hop count, relay duplicate/drop telemetry, and routing-control overhead are not measured by this run.</p><div class="charts">{figures}</div></html>'''
    (output_dir / "index.html").write_text(page)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sca", type=Path)
    parser.add_argument("vec", type=Path)
    parser.add_argument("rt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observation-start", type=float, required=True)
    parser.add_argument("--observation-end", type=float, required=True)
    parser.add_argument("--inifile", type=Path, default=Path("simulations/mesh/omnetpp.ini"))
    args = parser.parse_args()
    summary = generate(args.sca, args.vec, args.rt, args.output,
                       args.observation_start, args.observation_end, args.inifile)
    print(f"Dashboard: {args.output / 'index.html'}")
    print(f"AODV: {summary['received_unique_application_packets']}/{summary['generated_unique_application_packets']} unique packets; "
          f"PDR={summary['packet_delivery_ratio']:.4f}")
    delay = summary["mean_end_to_end_delay_s"]
    throughput = summary["throughput_bps"]
    print(f"Mean delay={delay*1000:.3f} ms" if delay is not None else "Mean delay=Not measured")
    print(f"Throughput={throughput:.1f} bit/s" if throughput is not None else "Throughput=Not measured")
    print("Packet-level hop count=Not measured")


if __name__ == "__main__":
    main()
