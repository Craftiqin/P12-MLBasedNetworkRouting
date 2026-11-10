from datetime import datetime, timezone

import pytest

from dashboard.p12_data import (
    delivery_intervals, format_metric, hardware_records, merge_incremental_records,
    parse_routing_response, parse_sensor_response,
    record_is_fresh,
)


def test_api_payload_parsers_reject_wrong_shapes():
    assert parse_sensor_response([]) == []
    with pytest.raises(ValueError):
        parse_sensor_response({"events": []})
    assert parse_routing_response({"events": [], "totalGatewayReceived": 0})["events"] == []
    with pytest.raises(ValueError):
        parse_routing_response({"events": [], "totalGatewayReceived": "0"})


def test_hardware_history_excludes_simulation_and_validation_records():
    rows = [
        {"provenance": "live_hardware", "temperatureC": 22},
        {"provenance": "api_validation", "temperatureC": 99},
        {"temperatureC": -100, "dataSource": "simulation"},
    ]
    assert hardware_records(rows) == [rows[0]]
    assert format_metric(None) == "N/A"
    assert format_metric(float("nan")) == "N/A"
    assert format_metric(-60, " dBm") == "-60.00 dBm"


def test_stale_and_missing_sensor_timestamps_are_not_live():
    now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    assert record_is_fresh({"receivedAt": "2026-11-09T11:59:46Z"}, now, 15)
    assert not record_is_fresh({"receivedAt": "2026-11-09T11:59:40Z"}, now, 15)
    assert not record_is_fresh({"receivedAt": "bad"}, now, 15)
    assert not record_is_fresh(None, now, 15)


def test_measured_delivery_intervals_and_missing_metrics():
    events = [
        {"receivedAt": "2026-11-09T00:00:00Z", "sourceUptimeMs": 100, "sourcePacketsSent": 4},
        {"receivedAt": "2026-11-09T00:00:05Z", "sourceUptimeMs": 5100, "sourcePacketsSent": 6},
        {"receivedAt": "2026-11-09T00:00:10Z", "sourceUptimeMs": 10100, "sourcePacketsSent": None},
        {"receivedAt": "2026-11-09T00:00:15Z", "sourceUptimeMs": 15100, "sourcePacketsSent": 8},
    ]
    intervals = delivery_intervals(events)
    assert len(intervals) == 1
    assert intervals[0]["attempts"] == 2
    assert intervals[0]["pdr"] == 0.5
    assert intervals[0]["loss"] == 0.5


def test_delivery_ratio_does_not_bridge_device_reboot():
    events = [
        {"receivedAt": "2026-11-09T00:00:00Z", "sourceUptimeMs": 10000, "sourcePacketsSent": 20},
        {"receivedAt": "2026-11-09T00:00:05Z", "sourceUptimeMs": 100, "sourcePacketsSent": 1},
        {"receivedAt": "2026-11-09T00:00:10Z", "sourceUptimeMs": 5100, "sourcePacketsSent": 2},
    ]
    stats = delivery_intervals(events)
    assert len(stats) == 1 and stats[0]["attempts"] == 1


def test_incremental_refresh_deduplicates_and_caps_by_received_time():
    previous = [
        {"id": 1, "sequence": 10, "receivedAt": "2026-11-10T00:00:01Z", "temperatureC": 21},
        {"id": 2, "sequence": 11, "receivedAt": "2026-11-10T00:00:02Z", "temperatureC": 22},
    ]
    incoming = [
        {"id": 2, "sequence": 11, "receivedAt": "2026-11-10T00:00:02Z", "temperatureC": 23},
        {"id": 3, "sequence": 12, "receivedAt": "2026-11-10T00:00:03Z", "temperatureC": 24},
    ]
    merged = merge_incremental_records(previous, incoming, 2)
    assert [row["id"] for row in merged] == [3, 2]
    assert merged[1]["temperatureC"] == 23
