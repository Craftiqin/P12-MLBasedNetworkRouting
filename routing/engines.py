from __future__ import annotations

import networkx as nx
import pandas as pd

from simulator.core import FEATURES, _shortest_path, link_features


def minimum_hop_next_hop(graph: nx.Graph, node: str, gateway: str) -> tuple[str | None, str]:
    path = _shortest_path(graph, node, gateway)
    return (path[1], "minimum_hop") if path and len(path) > 1 else (None, "route_unavailable")


def ml_next_hop(graph: nx.Graph, node: str, gateway: str, history: list[str],
                model, load: float, previous: str | None, margin: float = .08) -> tuple[str | None, str]:
    candidates=[]
    for neighbor in sorted(graph.neighbors(node)):
        if neighbor in history or not graph[node][neighbor].get("available",True):
            continue
        tail=_shortest_path(graph,neighbor,gateway)
        if not tail or node in tail:
            continue
        features=link_features(graph[node][neighbor],len(tail)-1,load)
        try:
            probability=float(model.predict_proba(pd.DataFrame([features],columns=FEATURES))[0][list(model.classes_).index(1)])
        except (ValueError,IndexError,AttributeError):
            continue
        tail_success=1.0
        for u,v in zip(tail,tail[1:]):
            tail_success *= 1-float(graph[u][v]["loss_probability"])
        candidates.append(((1-probability)+(1-tail_success),neighbor))
    if not candidates:
        return minimum_hop_next_hop(graph,node,gateway)[0], "baseline_fallback"
    candidates.sort(key=lambda item:(item[0],item[1]))
    best=candidates[0]
    old=next((c for c in candidates if c[1]==previous),None)
    return (old[1],"ml_hysteresis") if old and old[0] <= best[0]+margin else (best[1],"ml_probability_cost")
