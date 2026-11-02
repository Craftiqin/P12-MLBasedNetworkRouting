"""Safe candidate validation and deterministic fallback for inference."""

import math

FAILURE_PENALTY_MS = 1000.0


def expected_cost(pdr: float, latency_ms: float) -> float:
    return pdr * latency_ms + (1.0 - pdr) * FAILURE_PENALTY_MS


def select_safely(prediction: int, features: dict) -> int:
    """Return upper=0, lower=1, or -1 (drop); never return unavailable path."""
    def usable(prefix: str) -> bool:
        try:
            return (
                bool(features[f"{prefix}_available"])
                and math.isfinite(float(features[f"{prefix}_pdr_estimate"]))
                and 0 <= float(features[f"{prefix}_pdr_estimate"]) <= 1
                and math.isfinite(float(features[f"{prefix}_latency_ms"]))
                and float(features[f"{prefix}_latency_ms"]) >= 0
                and math.isfinite(float(features[f"{prefix}_hops"]))
                and float(features[f"{prefix}_hops"]) >= 1
            )
        except (KeyError, TypeError, ValueError):
            return False

    upper = usable("upper")
    lower = usable("lower")
    if prediction == 0 and upper:
        return 0
    if prediction == 1 and lower:
        return 1
    if not upper and not lower:
        return -1
    if not upper:
        return 1
    if not lower:
        return 0
    upper_cost = expected_cost(features["upper_pdr_estimate"], features["upper_latency_ms"])
    lower_cost = expected_cost(features["lower_pdr_estimate"], features["lower_latency_ms"])
    if upper_cost != lower_cost:
        return 0 if upper_cost < lower_cost else 1
    return 0 if features["upper_hops"] <= features["lower_hops"] else 1
