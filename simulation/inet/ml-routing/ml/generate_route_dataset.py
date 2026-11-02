#!/usr/bin/env python3
"""Generate controlled, synthetic route-choice scenarios (not hardware data)."""

import argparse
import csv
import random
from pathlib import Path

FIELDS = [
    "scenario_id", "seed", "split", "condition",
    "upper_available", "upper_pdr_estimate", "upper_latency_ms", "upper_hops",
    "lower_available", "lower_pdr_estimate", "lower_latency_ms", "lower_hops",
    "upper_expected_cost_ms", "lower_expected_cost_ms", "label_route",
    "label_reason", "data_origin",
]
FAILURE_PENALTY_MS = 1000.0

# Controlled route-level conditions. Values are scenario inputs, not measurements.
CONDITIONS = {
    "healthy": ((0.985, 34.0), (0.955, 47.0)),
    "degraded_reliability": ((0.79, 31.0), (0.955, 54.0)),
    "high_latency": ((0.985, 132.0), (0.96, 58.0)),
    "relay_failure": ((0.0, 1000.0), (0.95, 56.0)),
    "competing_paths": ((0.91, 23.0), (0.985, 73.0)),
    "combined_degradation": ((0.84, 118.0), (0.96, 62.0)),
}


def expected_cost(pdr: float, latency_ms: float) -> float:
    """Expected completion cost: delivered delay, else a 1 s failure penalty."""
    return pdr * latency_ms + (1.0 - pdr) * FAILURE_PENALTY_MS


def generate_rows(run_count: int = 100, seed: int = 20261101) -> list[dict]:
    rows = []
    for run_id in range(run_count):
        split = "train" if run_id < int(run_count * 0.8) else "test"
        for condition_index, (condition, paths) in enumerate(CONDITIONS.items()):
            rng = random.Random(seed + run_id * 997 + condition_index * 101)
            estimates = []
            for pdr_base, latency_base in paths:
                pdr = min(0.999, max(0.0, pdr_base + rng.gauss(0.0, 0.045)))
                latency = max(1.0, latency_base + rng.gauss(0.0, 8.0))
                estimates.append((pdr, latency))

            upper_available = int(condition != "relay_failure")
            lower_available = 1
            # Include rare no-route states, so the fallback/drop class is represented.
            if condition == "relay_failure" and run_id % 4 == 0:
                lower_available = 0

            pdr_u, delay_u = estimates[0]
            pdr_l, delay_l = estimates[1]
            cost_u = expected_cost(pdr_u, delay_u) if upper_available else FAILURE_PENALTY_MS
            cost_l = expected_cost(pdr_l, delay_l) if lower_available else FAILURE_PENALTY_MS
            if not upper_available and not lower_available:
                label, reason = -1, "no_valid_route"
            elif upper_available and (not lower_available or cost_u <= cost_l):
                label, reason = 0, "minimum_expected_completion_cost"
            else:
                label, reason = 1, "minimum_expected_completion_cost"

            rows.append({
                "scenario_id": f"run{run_id:03d}_{condition}",
                "seed": run_id,
                "split": split,
                "condition": condition,
                "upper_available": upper_available,
                "upper_pdr_estimate": round(pdr_u, 8),
                "upper_latency_ms": round(delay_u, 6),
                "upper_hops": 3,
                "lower_available": lower_available,
                "lower_pdr_estimate": round(pdr_l, 8),
                "lower_latency_ms": round(delay_l, 6),
                "lower_hops": 3,
                "upper_expected_cost_ms": round(cost_u, 6),
                "lower_expected_cost_ms": round(cost_l, 6),
                "label_route": label,
                "label_reason": reason,
                "data_origin": "synthetic_controlled_route_scenario",
            })
    return rows


def write_dataset(path: Path, run_count: int = 100, seed: int = 20261101) -> int:
    rows = generate_rows(run_count, seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("ml/data/route_scenarios.csv"))
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261101)
    args = parser.parse_args()
    print(f"wrote {write_dataset(args.output, args.runs, args.seed)} labeled synthetic scenarios to {args.output}")


if __name__ == "__main__":
    main()
