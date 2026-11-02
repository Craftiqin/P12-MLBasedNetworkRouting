from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Any

import networkx as nx
from metrics.core import summarize

FEATURES = ["rssi_dbm", "latency_ms", "loss_estimate", "throughput_kbps", "remaining_hops"]


@dataclass
class Link:
    available: bool = True
    rssi_dbm: float = -60.0
    loss_probability: float = 0.05
    latency_ms: float = 20.0
    capacity_kbps: float = 250.0
    congestion: float = 0.0


@dataclass
class Packet:
    packet_id: int
    source_id: str
    destination_id: str
    creation_time_s: float
    hop_count: int = 0
    hop_limit: int = 12
    history: list[str] = field(default_factory=list)
    payload_bytes: int = 64


@dataclass
class SimulationConfig:
    packet_count: int = 100
    packet_rate_pps: float = 5.0
    payload_bytes: int = 64
    hop_limit: int = 12
    seed: int = 17
    source: str = "S"
    gateway: str = "G"
    traffic_load: float = 0.0
    scenario: str = "normal"


def build_topology(node_count: int = 6, *, loss_probability: float = 0.05,
                   latency_ms: float = 20.0, rssi_dbm: float = -60.0,
                   capacity_kbps: float = 250.0) -> nx.Graph:
    if node_count < 6:
        raise ValueError("node_count must be at least 6")
    graph = nx.Graph()
    names = ["S", "G"] + [f"R{i}" for i in range(1, node_count - 1)]
    graph.add_nodes_from(names)
    # Two disjoint source-to-gateway corridors plus cross-links for alternatives.
    edges = [("S", "R1"), ("R1", "R2"), ("R2", "G"),
             ("S", "R3"), ("R3", "R4"), ("R4", "G"),
             ("R1", "R3"), ("R2", "R4")]
    for a, b in edges:
        if a in graph and b in graph:
            graph.add_edge(a, b, **Link(loss_probability=loss_probability,
                                         latency_ms=latency_ms,
                                         rssi_dbm=rssi_dbm,
                                         capacity_kbps=capacity_kbps).__dict__)
    # Additional relay nodes attach to the core, preserving at least two routes.
    for name in names[6:]:
        idx = int(name[1:])
        graph.add_edge(name, "R1" if idx % 2 == 0 else "R3",
                       **Link(loss_probability=loss_probability, latency_ms=latency_ms,
                              rssi_dbm=rssi_dbm, capacity_kbps=capacity_kbps).__dict__)
    return graph


def link_features(attrs: dict[str, Any], remaining_hops: int, load: float = 0.0) -> list[float]:
    cap = max(float(attrs["capacity_kbps"]), 1e-6)
    congestion = min(0.95, max(0.0, float(attrs.get("congestion", 0.0)) + load * 0.35))
    return [float(attrs["rssi_dbm"]), float(attrs["latency_ms"]) * (1 + congestion),
            min(1.0, float(attrs["loss_probability"]) + congestion * 0.4),
            cap * (1 - congestion), float(remaining_hops)]


def _scenario_graph(base: nx.Graph, scenario: str) -> nx.Graph:
    graph = base.copy()
    if scenario == "degraded":
        if graph.has_edge("S", "R1"):
            graph["S"]["R1"].update(rssi_dbm=-88.0, loss_probability=0.45, latency_ms=65.0)
    elif scenario == "preferred_link_failure":
        if graph.has_edge("S", "R1"):
            graph["S"]["R1"]["available"] = False
    elif scenario == "high_loss":
        for _, _, d in graph.edges(data=True): d["loss_probability"] = min(.8, d["loss_probability"] + .3)
    elif scenario == "high_latency":
        for _, _, d in graph.edges(data=True): d["latency_ms"] *= 3
    elif scenario == "congestion":
        for _, _, d in graph.edges(data=True): d["congestion"] = .7
    elif scenario == "recovery":
        # Preferred link is down for first half, then available again.
        if graph.has_edge("S", "R1"):
            graph["S"]["R1"]["available"] = False
    elif scenario != "normal":
        raise ValueError(f"unknown scenario: {scenario}")
    return graph


def _shortest_path(graph: nx.Graph, source: str, target: str) -> list[str] | None:
    usable = nx.Graph()
    usable.add_nodes_from(graph.nodes)
    usable.add_edges_from((a, b) for a, b, d in graph.edges(data=True) if d.get("available", True))
    try:
        paths = nx.all_shortest_paths(usable, source, target)
        return min((list(p) for p in paths), key=lambda p: tuple(p))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def run_simulation(base_graph: nx.Graph, config: SimulationConfig, routing: str = "baseline",
                   model: Any = None, *, events: bool = True) -> dict[str, Any]:
    graph = _scenario_graph(base_graph, config.scenario)
    edge_order = {tuple(sorted((a, b))): i for i, (a, b) in enumerate(sorted(graph.edges()))}
    now = 0.0
    records: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    if events and config.scenario in ("preferred_link_failure", "recovery"):
        event_rows.append({"packet_id":None,"time_s":0.0,"current_node":"S","next_hop":"R1",
                           "hop_count":0,"reason":config.scenario,"event":"link_failure"})
    if events and config.scenario == "degraded":
        event_rows.append({"packet_id":None,"time_s":0.0,"current_node":"S","next_hop":"R1",
                           "hop_count":0,"reason":"simulated_quality_degradation","event":"link_degradation"})
    seen: set[tuple[str, int]] = set()
    current_routes: dict[str, str] = {}
    route_switches = 0
    for pid in range(config.packet_count):
        created = pid / max(config.packet_rate_pps, 1e-6)
        now = max(now, created)
        packet = Packet(pid, config.source, config.gateway, created,
                        hop_limit=config.hop_limit, history=[config.source], payload_bytes=config.payload_bytes)
        delivered, status, hops = False, "route_unavailable", 0
        # Recovery scenario restores preferred route after failure interval.
        if config.scenario == "recovery" and pid >= config.packet_count // 2 and graph.has_edge("S", "R1"):
            graph["S"]["R1"]["available"] = True
            if events and pid == config.packet_count // 2:
                event_rows.append({"packet_id":None,"time_s":created,"current_node":"S","next_hop":"R1",
                                   "hop_count":0,"reason":"simulated_link_recovery","event":"link_recovery"})
        while packet.history[-1] != config.gateway:
            node = packet.history[-1]
            path = _shortest_path(graph, node, config.gateway)
            if not path:
                status = "route_unavailable"; break
            if routing not in ("baseline", "ml"):
                raise ValueError("routing must be 'baseline' or 'ml'")
            from routing.engines import minimum_hop_next_hop, ml_next_hop
            if routing == "baseline" or model is None:
                nxt, reason = minimum_hop_next_hop(graph,node,config.gateway)
            else:
                nxt, reason = ml_next_hop(graph,node,config.gateway,packet.history,model,
                                          config.traffic_load,current_routes.get(node))
            if nxt is None or hops >= packet.hop_limit:
                status = "hop_limit" if hops >= packet.hop_limit else "route_unavailable"; break
            if nxt in packet.history:
                status = "loop_prevented"; break
            prior = current_routes.get(node)
            if prior is not None and prior != nxt:
                route_switches += 1
                if events:
                    event_rows.append({"packet_id":pid,"time_s":now,"current_node":node,
                                       "next_hop":nxt,"hop_count":hops,
                                       "reason":f"next_hop_changed:{prior}->{nxt}","event":"route_change"})
            current_routes[node] = nxt
            attrs = graph[node][nxt]
            if events:
                event_rows.append({"packet_id": pid, "time_s": now, "current_node": node,
                                   "next_hop": nxt, "hop_count": hops, "reason": reason,
                                   "event": "forward"})
            if suppress_duplicate(seen, nxt, pid):
                status = "duplicate_suppressed"; break
            if not attrs.get("available", True):
                status = "link_unavailable"; break
            latency = max(0.0, float(attrs["latency_ms"])) * (1 + config.traffic_load + attrs.get("congestion", 0.0)) / 1000
            now += latency
            p_loss = min(.99, max(0.0, float(attrs["loss_probability"]) + config.traffic_load * .2))
            edge_idx = edge_order[tuple(sorted((node, nxt)))]
            # Common random draw per packet/link keeps paired algorithms comparable.
            link_rng = random.Random(config.seed + pid * 1_000_003 + edge_idx * 97_409)
            if link_rng.random() < p_loss:
                status = "packet_loss"
                if events: event_rows.append({"packet_id":pid,"time_s":now,"current_node":node,"next_hop":nxt,"hop_count":hops+1,"reason":"transmission_failed","event":"drop"})
                break
            packet.history.append(nxt); packet.hop_count += 1; hops += 1
        if packet.history[-1] == config.gateway:
            delivered, status = True, "delivered"
            if events: event_rows.append({"packet_id":pid,"time_s":now,"current_node":config.gateway,"next_hop":"","hop_count":hops,"reason":"gateway_received","event":"delivered"})
        records.append({"packet_id":pid,"created_s":created,"delivered":delivered,"status":status,
                        "latency_s":now-created if delivered else math.nan,"hop_count":hops,
                        "route":"->".join(packet.history),"payload_bytes":config.payload_bytes})
    import pandas as pd
    packets = pd.DataFrame(records)
    duration = max(config.packet_count / max(config.packet_rate_pps, 1e-6), 1e-6)
    metrics = summarize(packets,config.payload_bytes,duration)
    metrics.update({"route_switch_count":route_switches,"observation_duration_s":duration,
                    "recovery_time_s":math.nan})
    if config.scenario == "recovery":
        recovered = packets[(packets.packet_id >= config.packet_count//2) & packets.delivered]
        # Failure starts at simulation time zero; successful post-recovery delivery restores condition.
        if len(recovered): metrics["recovery_time_s"] = float(recovered.iloc[0].created_s)
    return {"metrics":metrics,"packets":packets,"events":event_rows,"graph":graph}


def suppress_duplicate(seen: set[tuple[str, int]], node: str, packet_id: int) -> bool:
    key=(node,packet_id)
    if key in seen:
        return True
    seen.add(key)
    return False
