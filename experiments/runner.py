from __future__ import annotations

from pathlib import Path

import pandas as pd

from ml.pipeline import train_model
from simulator.core import SimulationConfig, build_topology, run_simulation

SCENARIOS = ["normal", "degraded", "preferred_link_failure", "high_loss",
             "high_latency", "congestion", "recovery"]


def run_suite(*, trials: int = 5, packets: int = 100, seed: int = 17,
              output_dir: str | Path = "results/python", node_count: int = 6,
              model=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if model is None:
        model, _, _ = train_model(seed=seed)
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    graph = build_topology(node_count)
    rows = []
    for si, scenario in enumerate(SCENARIOS):
        for trial in range(trials):
            trial_seed = seed + si * 1000 + trial
            for router in ("baseline", "ml"):
                cfg = SimulationConfig(packet_count=packets, seed=trial_seed,
                                       scenario=scenario, traffic_load=.25 if scenario == "congestion" else 0)
                result = run_simulation(graph, cfg, router, model)
                rows.append({"scenario":scenario,"trial":trial,"seed":trial_seed,
                             "routing":router,**result["metrics"]})
    raw = pd.DataFrame(rows)
    raw.to_csv(output_dir / "trial_results.csv", index=False)
    agg = (raw.groupby(["scenario","routing"], as_index=False)
           .agg({"pdr":["mean","std"],"packet_loss_rate":["mean","std"],
                 "mean_latency_ms":["mean","std"],"median_latency_ms":["mean"],
                 "p95_latency_ms":["mean"],"throughput_kbps":["mean","std"],
                 "route_switch_count":["mean","std"],"recovery_time_s":["mean"]}))
    agg.columns = ["_".join(str(x) for x in col if x != "") if isinstance(col, tuple) else col for col in agg.columns]
    agg.to_csv(output_dir / "aggregate_results.csv", index=False)
    return raw, agg
