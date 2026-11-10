"""Inference and fail-closed gates for live P12 route observations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import json
import math
import os
from pathlib import Path
from typing import Any

from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[1]
ROUTE_DATA = ROOT / "simulation/inet/ml-routing/ml/data/route_scenarios.csv"
ROUTE_EXPORT = ROOT / "simulation/inet/ml-routing/ml/artifacts/route_tree-runtime-v2.json"
FEATURES = (
    "upper_available", "upper_pdr_estimate", "upper_latency_ms", "upper_hops",
    "lower_available", "lower_pdr_estimate", "lower_latency_ms", "lower_hops",
)


@dataclass(frozen=True)
class RoutePolicy:
    confidence_min: float | None
    improvement_min: float | None
    hysteresis_observations: int | None
    min_change_interval_seconds: float | None
    max_telemetry_age_seconds: float = 15.0
    calibration_id: str | None = None

    def __post_init__(self) -> None:
        if self.confidence_min is not None and not 0 <= self.confidence_min <= 1:
            raise ValueError("confidence_min must be between 0 and 1")
        if self.improvement_min is not None and not 0 <= self.improvement_min < 1:
            raise ValueError("improvement_min must be in [0, 1)")
        if self.hysteresis_observations is not None and self.hysteresis_observations < 1:
            raise ValueError("hysteresis_observations must be positive")
        if self.min_change_interval_seconds is not None and self.min_change_interval_seconds < 0:
            raise ValueError("invalid hysteresis or route-change interval")
        if self.max_telemetry_age_seconds <= 0:
            raise ValueError("max_telemetry_age_seconds must be positive")


def configured_route_policy() -> RoutePolicy | None:
    """Load calibrated control gates; missing config disables command eligibility."""
    names = (
        "P12_MIN_MODEL_CONFIDENCE", "P12_MIN_ROUTE_IMPROVEMENT",
        "P12_ROUTE_HYSTERESIS_OBSERVATIONS", "P12_MIN_ROUTE_CHANGE_INTERVAL_SECONDS",
    )
    raw = [os.environ.get(name) for name in names]
    calibration_id = os.environ.get("P12_ROUTE_CALIBRATION_ID")
    if (any(value is None or value == "" for value in raw)
            or os.environ.get("P12_ROUTE_CALIBRATION_VALIDATED") != "1"
            or not calibration_id):
        return None
    try:
        return RoutePolicy(float(raw[0]), float(raw[1]), int(raw[2]), float(raw[3]),
                           calibration_id=calibration_id)
    except ValueError:
        return None


def load_route_model() -> DecisionTreeClassifier:
    """Rebuild exact exported route tree from its committed train partition."""
    train_x: list[list[float]] = []
    train_y: list[int] = []
    with ROUTE_DATA.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["split"] == "train":
                train_x.append([float(row[name]) for name in FEATURES])
                train_y.append(int(row["label_route"]))
    if not train_x:
        raise RuntimeError("route model training partition is empty")
    model = DecisionTreeClassifier(max_depth=4, min_samples_leaf=3, random_state=20261101)
    model.fit(train_x, train_y)
    artifact = json.loads(ROUTE_EXPORT.read_text(encoding="utf-8"))
    tree = artifact["tree"]
    fitted = model.tree_
    if (list(map(int, fitted.feature)) != tree["feature"]
            or list(map(int, fitted.children_left)) != tree["children_left"]
            or list(map(int, fitted.children_right)) != tree["children_right"]
            or any(abs(float(a) - float(b)) > 1e-10 for a, b in zip(fitted.threshold, tree["threshold"], strict=True))):
        raise RuntimeError("reconstructed Python route model differs from committed runtime export")
    return model


def _event_features(event: dict[str, Any]) -> list[float] | None:
    if event.get("featureValid") is not True:
        return None
    upper = event.get("candidateUpper")
    lower = event.get("candidateLower")
    if not isinstance(upper, dict) or not isinstance(lower, dict):
        return None
    pairs = (upper, lower)
    values: list[float] = []
    for candidate in pairs:
        available = candidate.get("available")
        pdr, latency, hops = candidate.get("pdr"), candidate.get("latencyMs"), candidate.get("hops")
        if not isinstance(available, bool):
            return None
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
               for value in (pdr, latency, hops)):
            return None
        if not 0 <= pdr <= 1 or not 0 <= latency <= 65535 or not 1 <= hops <= 16:
            return None
        values.extend((float(available), float(pdr), float(latency), float(hops)))
    return values


def _safe_route(prediction: int, features: list[float]) -> int:
    candidates = (features[:4], features[4:])
    usable = [bool(c[0]) and math.isfinite(c[1]) and 0 <= c[1] <= 1
              and math.isfinite(c[2]) and c[2] >= 0 and math.isfinite(c[3]) and c[3] >= 1
              for c in candidates]
    if prediction in (0, 1) and usable[prediction]:
        return prediction
    if not any(usable):
        return -1
    if not usable[0]:
        return 1
    if not usable[1]:
        return 0
    costs = [c[1] * c[2] + (1 - c[1]) * 1000.0 for c in candidates]
    return min((0, 1), key=lambda i: (costs[i], candidates[i][3], i))


def advance_hysteresis(
    previous_signature: tuple[Any, ...] | None, previous_count: int,
    previous_evidence: tuple[Any, ...] | None, signature: tuple[Any, ...] | None,
    evidence: tuple[Any, ...], eligible_candidate: bool,
) -> tuple[tuple[Any, ...] | None, int, tuple[Any, ...]]:
    """Count each distinct fresh evidence event once; reset on ineligible input."""
    if not eligible_candidate or signature is None:
        return None, 0, evidence
    if evidence == previous_evidence:
        if signature == previous_signature:
            return previous_signature, previous_count, previous_evidence or evidence
        return signature, 1, previous_evidence or evidence
    count = previous_count + 1 if signature == previous_signature else 1
    return signature, count, evidence


def evaluate_live_route(
    event: dict[str, Any], *, model: DecisionTreeClassifier, policy: RoutePolicy,
    active_next_hop: int | None, now: datetime | None = None,
    last_route_change_at: datetime | None = None, repeated_candidate_count: int = 1,
) -> dict[str, Any]:
    """Evaluate one persisted source routing event; never emits a command."""
    now = now or datetime.now(timezone.utc)
    received = event.get("receivedAt")
    try:
        observed = datetime.fromisoformat(str(received).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return {"decision": "HOLD", "reason": "missing_or_invalid_timestamp"}
    age = (now - observed).total_seconds()
    if age < 0 or age > policy.max_telemetry_age_seconds:
        return {"decision": "HOLD", "reason": "stale_telemetry", "ageSeconds": age}
    if event.get("routingMode") == "NO_VALID_ROUTE":
        return {"decision": "HOLD", "reason": "source_reports_no_valid_route"}
    features = _event_features(event)
    if features is None:
        return {"decision": "HOLD", "reason": "incomplete_or_invalid_candidate_metrics"}
    pred = int(model.predict([features])[0])
    probabilities = model.predict_proba([features])[0]
    selected_index = _safe_route(pred, features)
    if selected_index not in (0, 1):
        return {"decision": "HOLD", "reason": "model_has_no_reachable_route", "prediction": pred,
                "confidence": float(max(probabilities))}
    confidence = float(probabilities[list(model.classes_).index(selected_index)])
    selected = 2 if selected_index == 0 else 3
    active_index = 0 if active_next_hop == 2 else 1 if active_next_hop == 3 else None
    candidate_costs = [
        values[1] * values[2] + (1 - values[1]) * 1000.0
        for values in (features[0:4], features[4:8])
    ]
    improvement = None
    if active_index is not None:
        old_cost, new_cost = candidate_costs[active_index], candidate_costs[selected_index]
        improvement = (old_cost - new_cost) / old_cost if old_cost > 0 else 0.0
    result = {"decision": "HOLD", "reason": "route_unchanged", "prediction": pred,
              "nextHopId": selected, "confidence": confidence, "improvement": improvement,
              "modelVersion": "decision-tree-v1-seed-20261101"}
    if selected == active_next_hop:
        return result
    if (not policy.calibration_id or policy.confidence_min is None or policy.improvement_min is None
            or policy.hysteresis_observations is None or policy.min_change_interval_seconds is None):
        result["reason"] = "validated_calibration_or_thresholds_not_configured"
        return result
    if confidence < policy.confidence_min:
        result["reason"] = "confidence_below_threshold"
        return result
    if improvement is None or improvement < policy.improvement_min:
        result["reason"] = "improvement_below_threshold_or_unknown"
        return result
    if repeated_candidate_count < policy.hysteresis_observations:
        result["reason"] = "hysteresis_not_satisfied"
        return result
    if last_route_change_at is not None:
        elapsed = (now - last_route_change_at).total_seconds()
        if elapsed < policy.min_change_interval_seconds:
            result["reason"] = "minimum_change_interval"
            return result
    result.update(decision="ELIGIBLE", reason="policy_gates_satisfied")
    return result
