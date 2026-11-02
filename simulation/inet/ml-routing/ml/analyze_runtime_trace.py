#!/usr/bin/env python3
"""Validate ML forwarding events and derive packet metrics from runtime CSV."""

import argparse
import csv
import html
import json
import statistics
from pathlib import Path

ROUTES = {"upper": [5, 2, 1, 0], "lower": [5, 4, 3, 0]}


def _svg(title, body, x_label="", y_label=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="820" height="370" viewBox="0 0 820 370" role="img" aria-label="{html.escape(title)}">
<rect width="100%" height="100%" fill="#fff"/><text x="410" y="30" text-anchor="middle" font-size="20" font-family="sans-serif">{html.escape(title)}</text>
{body}<text x="410" y="355" text-anchor="middle" font-size="13" font-family="sans-serif">{html.escape(x_label)}</text>
<text transform="translate(18 190) rotate(-90)" text-anchor="middle" font-size="13" font-family="sans-serif">{html.escape(y_label)}</text></svg>'''


def _bar_svg(title, value, maximum, label, x_label, y_label):
    body = '<path d="M85 300 H770 M85 70 V300" stroke="#64748b" fill="none"/>'
    if value is None:
        body += '<text x="420" y="185" text-anchor="middle" font-size="20" fill="#64748b">Not measured</text>'
    else:
        height = 210 * value / max(maximum, 1e-9)
        y = 300 - height
        body += f'<rect x="330" y="{y:.1f}" width="180" height="{height:.1f}" fill="#267a63" rx="6"/>'
        body += f'<text x="420" y="{y-12:.1f}" text-anchor="middle" font-size="15">{html.escape(label)}</text>'
    return _svg(title, body, x_label, y_label)


def _write_dashboard(output_dir, events, outcomes, metrics, *, failure_time=None):
    dashboard = output_dir / "dashboard"
    dashboard.mkdir(parents=True, exist_ok=True)
    delays = [row["delay_ms"] for row in outcomes if row["delay_ms"] is not None]
    maximum_delay = max(delays, default=1.0)
    bins = [0] * 8
    for delay in delays:
        bins[min(7, int(delay / max(maximum_delay, 1e-9) * 8))] += 1
    body = '<path d="M85 300 H770 M85 70 V300" stroke="#64748b" fill="none"/>'
    max_bin = max(bins, default=1)
    for index, count in enumerate(bins):
        height = 210 * count / max(max_bin, 1)
        x = 100 + index * 80
        body += f'<rect x="{x}" y="{300-height:.1f}" width="54" height="{height:.1f}" fill="#3478a8"/>'
        body += f'<text x="{x+27}" y="320" text-anchor="middle" font-size="10">bin {index+1}</text>'
    (dashboard / "02-delay.svg").write_text(_svg("End-to-end delay distribution", body, "Observed delay bin", "Delivered packets"))
    (dashboard / "01-pdr.svg").write_text(_bar_svg("Packet delivery ratio (ML run)", metrics["pdr"], 1.0,
                                  f'{metrics["pdr"]:.3f}', "ML application packets", "PDR"))
    (dashboard / "03-throughput.svg").write_text(_bar_svg("Application throughput", metrics["throughput_bit_s"],
                                  max(metrics["throughput_bit_s"], 1) * 1.2,
                                  f'{metrics["throughput_bit_s"]:.1f} bit/s', "ML run", "Throughput (bit/s)"))
    hop_value = metrics["mean_packet_hops"]
    (dashboard / "04-hop-count.svg").write_text(_bar_svg("Packet-level hop count", hop_value,
                                  max(hop_value or 1, 1) * 1.2, "Not measured" if hop_value is None else f'{hop_value:.2f}',
                                  "Delivered application packets", "Mean hops"))

    decisions = [row for row in events if row["event"] == "decision" and int(row["node_id"]) == 5]
    end_time = max((float(row["time_s"]) for row in events), default=1.0)
    route_body = '<path d="M85 300 H770 M85 70 V300" stroke="#64748b" fill="none"/>'
    if failure_time is not None:
        x = 85 + 685 * failure_time / max(end_time, failure_time, 1e-9)
        route_body += f'<path d="M{x:.1f} 60 V300" stroke="#bd3b34" stroke-dasharray="6 5"/><text x="{x+4:.1f}" y="55" fill="#bd3b34" font-size="11">failure {failure_time:g}s</text>'
    coords = []
    for row in decisions:
        x = 85 + 685 * float(row["time_s"]) / max(end_time, 1e-9)
        route = row["selected_route"]
        y = 135 if route == "upper" else 220 if route == "lower" else 285
        coords.append((x, y, route))
    for previous, current in zip(coords, coords[1:]):
        route_body += f'<path d="M{previous[0]:.1f} {previous[1]} H{current[0]:.1f} V{current[1]}" stroke="#267a63" stroke-width="2" fill="none"/>'
    for x, y, route in coords[::max(1, len(coords)//60)]:
        route_body += f'<circle cx="{x:.1f}" cy="{y}" r="3" fill="#267a63"><title>{route}</title></circle>'
    for y, name in ((135, "upper"), (220, "lower"), (285, "no route")):
        route_body += f'<text x="78" y="{y+4}" text-anchor="end" font-size="11">{name}</text>'
    (dashboard / "05-route-recovery.svg").write_text(_svg("Selected ML route over simulation time", route_body,
                                  "Simulation time (s)", "Selected route"))

    generated_times = sorted(float(row["generated_time_s"]) for row in outcomes)
    delivered_times = sorted(float(row["received_time_s"]) for row in outcomes if row["received_time_s"] is not None)
    max_time = max([end_time, 1.0])
    timeline_body = '<path d="M85 300 H770 M85 70 V300" stroke="#64748b" fill="none"/>'
    for values, color in ((generated_times, "#3478a8"), (delivered_times, "#267a63")):
        points = []
        for index, time in enumerate(values):
            x = 85 + 685 * time / max_time
            y = 300 - 210 * (index + 1) / max(len(generated_times), 1)
            points.append(f"{x:.1f},{y:.1f}")
        if points:
            timeline_body += f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"/>'
    timeline_body += '<text x="590" y="90" fill="#3478a8" font-size="13">generated</text><text x="590" y="112" fill="#267a63" font-size="13">delivered</text>'
    (dashboard / "06-delivery-timeline.svg").write_text(_svg("Cumulative packet generation and delivery", timeline_body,
                                  "Simulation time (s)", "Cumulative packets"))

    cards = [
        ("Generated / received", f'{metrics["packets_generated"]} / {metrics["packets_received_unique"]}'),
        ("PDR", f'{metrics["pdr"]:.4f}'),
        ("Mean delay", "Not measured" if metrics["mean_delay_ms"] is None else f'{metrics["mean_delay_ms"]:.3f} ms'),
        ("Throughput", f'{metrics["throughput_bit_s"]:.1f} bit/s'),
        ("Mean packet hops", "Not measured" if hop_value is None else f'{hop_value:.2f}'),
        ("Route changes / recovery", f'{metrics["route_changes"]} / {metrics["route_recovery_s"] if metrics["route_recovery_s"] is not None else "Not measured"}'),
    ]
    card_html = "".join(f'<article><small>{html.escape(label)}</small><strong>{html.escape(value)}</strong></article>' for label, value in cards)
    imgs = "".join(f'<section><img src="{name}" alt="{html.escape(title)}"></section>' for name, title in [
        ("01-pdr.svg", "Packet delivery ratio"), ("02-delay.svg", "End to end delay"),
        ("03-throughput.svg", "Throughput"), ("04-hop-count.svg", "Packet hop count"),
        ("05-route-recovery.svg", "Route selection timeline"), ("06-delivery-timeline.svg", "Packet delivery timeline")])
    provenance = html.escape(metrics["data_origin"])
    (dashboard / "index.html").write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ML routing experiment</title><style>body{{font:15px system-ui;background:#f4f6f8;color:#19232d;margin:2rem}}h1{{margin-bottom:.25rem}}.note{{color:#52616d}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:1.5rem 0}}article,section{{background:white;border:1px solid #d9e0e6;border-radius:10px;padding:12px}}article strong{{display:block;font-size:1.25rem;margin-top:8px}}.plots{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:12px}}img{{width:100%;height:auto}}code{{overflow-wrap:anywhere}}</style>
<h1>ML Decision Tree routing</h1><p class="note">Model {html.escape(metrics['model_version'])}. Data source: {provenance}. Link PDR/latency features are configured estimates, not measured radio observations.</p>
<div class="cards">{card_html}</div><div class="plots">{imgs}</div><p class="note">Routing control overhead: Not measured. Single simulation run; variability across seeds not available. See packet_outcomes.csv and events.csv for packet ledger and route-decision evidence.</p></html>''')


def analyze(events_path: Path, output_dir: Path, *, payload_bytes=128,
            observation_seconds=56.0, failure_time=None, restart_time=None):
    with events_path.open(newline="") as stream:
        events = list(csv.DictReader(stream))
    generated = {}
    delivered = {}
    for event in events:
        packet_id = int(event["packet_id"])
        kind = event["event"]
        if kind == "packet_generated" and int(event["node_id"]) == 5:
            generated[packet_id] = event
        elif kind == "packet_delivered" and int(event["node_id"]) == 0:
            delivered.setdefault(packet_id, event)

    outcomes = []
    delays = []
    hops = []
    for packet_id, sent in sorted(generated.items()):
        received = delivered.get(packet_id)
        sent_time = float(sent["time_s"])
        received_time = float(received["time_s"]) if received else None
        delay_ms = (received_time - sent_time) * 1000 if received else None
        hop_count = int(received["hops"]) if received else None
        if received:
            delays.append(delay_ms)
            hops.append(hop_count)
        drops = [e for e in events if int(e["packet_id"]) == packet_id and e["event"] in {
            "no_route_drop", "duplicate_drop", "loop_drop", "hop_limit_drop", "packet_not_delivered"}]
        explicit_drops = [e for e in drops if e["event"] != "packet_not_delivered"]
        route = sent["route"]
        outcomes.append({
            "packet_id": packet_id,
            "source_node": 5,
            "destination_node": 0,
            "route": route,
            "generated_time_s": sent_time,
            "received_time_s": received_time,
            "delay_ms": delay_ms,
            "hop_count": hop_count,
            "status": "delivered" if received else "not_received_by_end",
            "drop_reason": (explicit_drops[-1]["detail"] if explicit_drops else
                            drops[-1]["detail"] if drops else ("" if received else "no_destination_event")),
        })

    decisions = [e for e in events if e["event"] == "decision" and int(e["node_id"]) == 5]
    selected = [e["selected_route"] for e in decisions]
    route_changes = sum(a != b for a, b in zip(selected, selected[1:]))
    failure_events = [e for e in events if e["event"] == "failure_detected"]
    failure_detected = min((float(e["time_s"]) for e in failure_events), default=None)
    route_change_times = [float(current["time_s"]) for previous, current in zip(decisions, decisions[1:])
                          if previous["selected_route"] != current["selected_route"]]
    route_change_time = min((t for t in route_change_times if failure_time is None or t >= failure_time), default=None)
    probe_success_events = [e for e in events if e["event"] == "path_probe_success"]
    probe_success_time = min((float(e["time_s"]) for e in probe_success_events), default=None)
    recovered_path_eligible = any(
        e["route"] == e["selected_route"]
        and float(e["time_s"]) > float(success["time_s"])
        and float(e[f"{e['route']}_available"]) == 1.0
        for success in probe_success_events
        for e in decisions if e["route"] == success["route"]
    )
    route_proofs = []
    path_errors = []
    for packet_id, sent in generated.items():
        route = sent["route"]
        if route not in ROUTES:
            continue
        expected = ROUTES[route]
        forwards = sorted((e for e in events if int(e["packet_id"]) == packet_id and e["event"] == "packet_forwarded"),
                          key=lambda e: float(e["time_s"]))
        delivered_event = delivered.get(packet_id)
        actual_edges = [(int(e["node_id"]), int(e["next_hop_id"])) for e in forwards]
        expected_edges = list(zip(expected[1:-1], expected[2:]))
        first_hop = int(sent["next_hop_id"])
        if delivered_event and first_hop == expected[1] and actual_edges == expected_edges and int(delivered_event["hops"]) == len(expected) - 1:
            route_proofs.append(packet_id)
        elif delivered_event:
            path_errors.append(packet_id)

    generated_ids = set(generated)
    delivered_ids = set(delivered) & generated_ids
    received_after_failure = [float(e["time_s"]) for e in delivered.values()
                              if failure_time is not None and float(e["time_s"]) >= failure_time]
    recovery = min(received_after_failure) - failure_time if received_after_failure else None
    first_service_delivery = min(received_after_failure, default=None)
    lost_during_event = sum(
        1 for packet_id, sent in generated.items()
        if failure_time is not None and first_service_delivery is not None
        and failure_time <= float(sent["time_s"]) < first_service_delivery
        and packet_id not in delivered
    )
    lost_during_outage = sum(
        1 for packet_id, sent in generated.items()
        if failure_time is not None and restart_time is not None
        and failure_time <= float(sent["time_s"]) < restart_time and packet_id not in delivered
    )
    metrics = {
        "routing": "ML Decision Tree application-level next-hop forwarding",
        "model_version": events[0]["model_version"] if events else "unknown",
        "packets_generated": len(generated_ids),
        "packets_received_unique": len(delivered_ids),
        "packets_lost_by_end": len(generated_ids - delivered_ids),
        "pdr": len(delivered_ids) / len(generated_ids) if generated_ids else 0.0,
        "packet_loss_ratio": 1 - len(delivered_ids) / len(generated_ids) if generated_ids else 0.0,
        "mean_delay_ms": statistics.mean(delays) if delays else None,
        "throughput_bit_s": len(delivered_ids) * payload_bytes * 8 / observation_seconds,
        "mean_packet_hops": statistics.mean(hops) if hops else None,
        "route_changes": route_changes,
        "route_recovery_s": recovery,
        "failure_time_s": failure_time,
        "failure_detection_time_s": failure_detected,
        "failure_detection_latency_s": (failure_detected - failure_time
                                          if failure_detected is not None and failure_time is not None else None),
        "route_change_time_s": route_change_time,
        "route_change_latency_s": (route_change_time - failure_time
                                    if route_change_time is not None and failure_time is not None else None),
        "restart_time_s": restart_time,
        "active_probe_success_time_s": probe_success_time,
        "active_probe_success_latency_s": (probe_success_time - restart_time
                                            if probe_success_time is not None and restart_time is not None else None),
        "recovered_path_eligible": recovered_path_eligible,
        "packets_lost_during_failure_to_service_recovery": lost_during_event,
        "packets_lost_during_failure_interval": lost_during_outage,
        "duplicate_drops": sum(e["event"] == "duplicate_drop" for e in events),
        "loop_drops": sum(e["event"] == "loop_drop" for e in events),
        "hop_limit_drops": sum(e["event"] == "hop_limit_drop" for e in events),
        "routing_control_overhead": "Not measured",
        "valid_delivered_path_count": len(route_proofs),
        "delivered_path_errors": path_errors,
        "data_origin": "OMNeT++/INET simulation events; model features are configured route estimates plus runtime NodeStatus availability",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "packet_outcomes.csv").open("w", newline="") as stream:
        fields = ["packet_id", "source_node", "destination_node", "route", "generated_time_s",
                  "received_time_s", "delay_ms", "hop_count", "status", "drop_reason"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(outcomes)
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    _write_dashboard(output_dir, events, outcomes, metrics, failure_time=failure_time)
    if path_errors:
        raise ValueError(f"delivered packets did not follow selected route: {path_errors[:10]}")
    if len(route_proofs) != len(delivered_ids):
        raise ValueError("not every delivered packet has a verified hop-by-hop route trace")
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--payload-bytes", type=int, default=128)
    parser.add_argument("--observation-seconds", type=float, default=56.0)
    parser.add_argument("--failure-time", type=float)
    parser.add_argument("--restart-time", type=float)
    args = parser.parse_args()
    print(json.dumps(analyze(args.events, args.output_dir, payload_bytes=args.payload_bytes,
                             observation_seconds=args.observation_seconds, failure_time=args.failure_time,
                             restart_time=args.restart_time), indent=2))


if __name__ == "__main__":
    main()
