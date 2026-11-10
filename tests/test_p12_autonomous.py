from datetime import datetime, timedelta, timezone

from dashboard.autonomous import (
    RoutePolicy, advance_hysteresis, compare_route_performance,
    evaluate_live_route, load_route_model,
)


def test_python_route_model_matches_exported_tree():
    model = load_route_model()
    assert model.n_features_in_ == 8
    assert list(model.classes_) == [-1, 0, 1]


def _event(now, *, upper_available=True, lower_available=True):
    return {
        "receivedAt": now.isoformat(), "routingMode": "BASELINE_FALLBACK",
        "featureValid": True,
        "candidateUpper": {"available": upper_available, "pdr": 0.96, "latencyMs": 10.0, "hops": 2.0},
        "candidateLower": {"available": lower_available, "pdr": 0.65, "latencyMs": 90.0, "hops": 2.0},
    }


def test_stale_live_event_fails_closed():
    now = datetime.now(timezone.utc)
    result = evaluate_live_route(
        _event(now - timedelta(seconds=20)), model=load_route_model(),
        policy=RoutePolicy(.5, .05, 1, 0, 15), active_next_hop=3, now=now,
    )
    assert result["decision"] == "HOLD"
    assert result["reason"] == "stale_telemetry"


def test_incomplete_metrics_fail_closed():
    now = datetime.now(timezone.utc)
    event = _event(now)
    event["candidateUpper"]["latencyMs"] = None
    result = evaluate_live_route(
        event, model=load_route_model(), policy=RoutePolicy(.5, .05, 1, 0),
        active_next_hop=3, now=now,
    )
    assert result == {"decision": "HOLD", "reason": "incomplete_or_invalid_candidate_metrics"}


def test_model_will_not_select_unreachable_neighbor():
    now = datetime.now(timezone.utc)
    result = evaluate_live_route(
        _event(now, upper_available=False), model=load_route_model(),
        policy=RoutePolicy(0, 0, 1, 0), active_next_hop=3, now=now,
    )
    assert result["nextHopId"] == 3
    assert result["decision"] == "HOLD"
    assert result["reason"] == "route_unchanged"


def test_hysteresis_and_minimum_improvement_gate_candidate():
    now = datetime.now(timezone.utc)
    result = evaluate_live_route(
        _event(now), model=load_route_model(),
        policy=RoutePolicy(0, .99, 2, 60, calibration_id="test-calibration"), active_next_hop=3,
        now=now, last_route_change_at=now - timedelta(seconds=10), repeated_candidate_count=1,
    )
    assert result["decision"] == "HOLD"
    assert result["reason"] == "improvement_below_threshold_or_unknown"


def test_confidence_gate_blocks_low_confidence_policy():
    now = datetime.now(timezone.utc)
    result = evaluate_live_route(
        _event(now), model=load_route_model(), policy=RoutePolicy(1.0, 0, 1, 0, calibration_id="test-calibration"),
        active_next_hop=3, now=now,
    )
    assert result["decision"] == "HOLD"
    assert result["reason"] == "confidence_below_threshold"


def test_unconfigured_calibration_never_marks_route_eligible():
    now = datetime.now(timezone.utc)
    result = evaluate_live_route(
        _event(now), model=load_route_model(), policy=RoutePolicy(None, None, None, None),
        active_next_hop=3, now=now,
    )
    assert result["decision"] == "HOLD"
    assert result["reason"] == "validated_calibration_or_thresholds_not_configured"


def test_eligible_shadow_route_reports_candidate_and_measured_improvement():
    now = datetime.now(timezone.utc)
    result = evaluate_live_route(
        _event(now), model=load_route_model(),
        policy=RoutePolicy(.9, .1, 2, 60, calibration_id="fixture-calibration"),
        active_next_hop=3, now=now, last_route_change_at=now - timedelta(seconds=120),
        repeated_candidate_count=2,
    )
    assert result["decision"] == "ELIGIBLE"
    assert result["nextHopId"] == 2
    assert result["confidence"] >= .9
    assert result["improvement"] >= .1


def test_hysteresis_counts_distinct_eligible_events_once_and_resets():
    signature = (3, 2, "model-v1", 7)
    first = advance_hysteresis(None, 0, None, signature, (74, 47000), True)
    repeated = advance_hysteresis(*first[:2], first[2], signature, (74, 47000), True)
    second = advance_hysteresis(*repeated[:2], repeated[2], signature, (75, 49000), True)
    reset = advance_hysteresis(*second[:2], second[2], signature, (76, 51000), False)
    assert first[1] == 1 and repeated[1] == 1 and second[1] == 2
    assert reset[0] is None and reset[1] == 0


def test_command_feedback_compares_route_matched_gateway_intervals():
    start = datetime.now(timezone.utc)
    rows = []
    for idx, (hop, sent) in enumerate(((3, 10), (3, 20), (3, 30), (2, 40), (2, 42), (2, 44))):
        at = start + timedelta(seconds=idx * 5)
        rows.append({"receivedAt": at.isoformat(), "selectedNextHopId": hop,
                     "sourcePacketsSent": sent, "sourceUptimeMs": sent * 1000})
    result = compare_route_performance(rows, start + timedelta(seconds=15), 3, 2)
    assert result["status"] == "IMPROVED"
    assert result["beforePdr"] == .1 and result["afterPdr"] == .5


def test_command_feedback_stays_insufficient_without_post_change_windows():
    now = datetime.now(timezone.utc)
    result = compare_route_performance([], now, 3, 2)
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
