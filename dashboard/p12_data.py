"""Strict parsers and freshness metrics for the P12 read-only dashboard."""
from datetime import datetime, timezone
import math
from typing import Any


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def parse_sensor_response(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        raise ValueError("Sensor API response must be an array of records")
    return payload


def parse_routing_response(payload: Any) -> dict[str, Any]:
    if (not isinstance(payload, dict) or not isinstance(payload.get("events"), list)
            or any(not isinstance(row, dict) for row in payload["events"])):
        raise ValueError("Routing API response must contain an events array")
    total = payload.get("totalGatewayReceived")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise ValueError("Routing API response has invalid totalGatewayReceived")
    return payload


def merge_incremental_records(
    previous: list[dict[str, Any]], incoming: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    """Merge overlapping recent-rows snapshots by DB identity, newest receivedAt first."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in (*previous, *incoming):
        if not isinstance(row, dict):
            continue
        record_id = row.get("id")
        if record_id is not None:
            key = ("id", str(record_id))
        else:
            key = tuple(row.get(field) for field in (
                "projectId", "networkId", "sourceNodeId", "experimentId", "sequence", "sourceUptimeMs"
            ))
            if any(value is None for value in key):
                timestamp = row.get("receivedAt") or row.get("observedAt")
                key = ("timestamp", timestamp, row.get("sequence"), row.get("sourceNodeId"))
        merged[key] = row
    ordered = sorted(
        merged.values(),
        key=lambda row: parse_timestamp(row.get("receivedAt") or row.get("observedAt"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return ordered[:limit]


def hardware_records(readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select only persisted physical provenance; never infer it from values."""
    return [row for row in readings if row.get("provenance") == "live_hardware"]


def record_is_fresh(record: dict[str, Any] | None, now: datetime, max_age_seconds: int = 15) -> bool:
    timestamp = parse_timestamp((record or {}).get("receivedAt"))
    if timestamp is None:
        return False
    age = (now - timestamp).total_seconds()
    return 0 <= age <= max_age_seconds


def format_metric(value: Any, suffix: str = "", digits: int = 2) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "N/A"
    try:
        if value != value or value in (float("inf"), float("-inf")):
            return "N/A"
    except TypeError:
        return "N/A"
    return f"{value:.{digits}f}{suffix}"


def timestamped_values(records: list[dict[str, Any]], value_key: str,
                      timestamp_key: str = "receivedAt") -> list[tuple[datetime, float, Any]]:
    """Prepare only recorded finite values; missing samples remain gaps."""
    points = []
    for row in records:
        timestamp = parse_timestamp(row.get(timestamp_key))
        value = row.get(value_key)
        if timestamp and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            points.append((timestamp, float(value), row.get("sequence")))
    return sorted(points, key=lambda point: point[0])


def delivery_intervals(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return measured per-delivery interval PDR from source sent-counter deltas."""
    ordered = sorted(events, key=lambda row: parse_timestamp(row.get("receivedAt")) or datetime.min.replace(tzinfo=timezone.utc))
    result: list[dict[str, Any]] = []
    previous_sent = None
    previous_uptime = None
    for row in ordered:
        sent, uptime = row.get("sourcePacketsSent"), row.get("sourceUptimeMs")
        if not isinstance(sent, int) or isinstance(sent, bool) or not isinstance(uptime, int) or isinstance(uptime, bool):
            previous_sent, previous_uptime = None, None
            continue
        if previous_sent is not None and sent > previous_sent and uptime >= (previous_uptime or 0):
            attempts = sent - previous_sent
            result.append({
                "timestamp": row.get("observedAt") or row.get("receivedAt"),
                "pdr": 1.0 / attempts,
                "loss": (attempts - 1.0) / attempts,
                "attempts": attempts,
                "delivered": 1,
            })
        previous_sent, previous_uptime = sent, uptime
    return result
