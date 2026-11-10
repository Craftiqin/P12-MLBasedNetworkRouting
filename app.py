import json
import os
from uuid import NAMESPACE_URL, uuid5
from datetime import datetime, timezone
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dashboard.p12_data import (
    delivery_intervals, format_metric, hardware_records, merge_incremental_records,
    parse_routing_response, parse_sensor_response,
    parse_timestamp, record_is_fresh, timestamped_values,
)
from dashboard.autonomous import (
    RoutePolicy, advance_hysteresis, configured_route_policy,
    compare_route_performance, evaluate_live_route, load_route_model,
)

P12_API_URL = "https://api.craftiq.in/p12/iot-data"
P12_ROUTING_API_URL = "https://api.craftiq.in/p12/routing-events"
P12_CONTROL_API_URL = "https://api.craftiq.in/p12/routing-control"
P12_COMMANDS_API_URL = "https://api.craftiq.in/p12/routing-commands"
P12_STALE_AFTER_SECONDS = 15


@st.cache_resource
def _p12_route_model():
    return load_route_model()


def _number(value, suffix="", digits=2):
    return format_metric(value, suffix, digits)


def _percentage(value):
    return _number(value * 100 if isinstance(value, (int, float)) and not isinstance(value, bool) else None, "%")


def _p12_api_token():
    token = os.environ.get("P12_IOT_INGEST_TOKEN", "")
    if token:
        return token
    try:
        return str(st.secrets.get("P12_IOT_INGEST_TOKEN", ""))
    except Exception:
        return ""


def _p12_control_request(method, url, token, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "P12-IOT-Streamlit/2.0"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=8) as response:
        return json.loads(response.read())


def _p12_request_error(exc):
    if isinstance(exc, HTTPError) and exc.code in (401, 403):
        return (f"Cloudflare Worker rejected P12_IOT_INGEST_TOKEN (HTTP {exc.code}). "
                "Check that it matches the deployed smart-crop-api Worker secret.")
    return str(exc)


def _render_topology(event, routing_fresh, gateway_fresh, sensor):
    positions = {1: (0.08, 0.5), 2: (0.39, 0.78), 3: (0.39, 0.22), 4: (0.83, 0.5)}
    selected = event.get("selectedNextHopId") if event and routing_fresh else None
    candidates = {
        2: event.get("candidateUpper") if event and isinstance(event.get("candidateUpper"), dict) else {},
        3: event.get("candidateLower") if event and isinstance(event.get("candidateLower"), dict) else {},
    }
    fig = go.Figure()
    for relay, metrics in candidates.items():
        availability = metrics.get("available") if routing_fresh else None
        active = selected == relay and availability is True
        color = "#39d7bd" if active else "#7892b1" if availability is True else "#ed6b78" if availability is False else "#526174"
        dash = "solid" if availability is True else "dash"
        width = 4 if active else 2
        x1, y1 = positions[1]
        xm, ym = positions[relay]
        x4, y4 = positions[4]
        hover = (f"ESP32_01 → ESP32_{relay} → ESP32_04<br>Availability: {availability if availability is not None else 'unknown'}"
                 f"<br>Candidate PDR: {_percentage(metrics.get('pdr'))}"
                 f"<br>Candidate latency: {_number(metrics.get('latencyMs'), ' ms')}"
                 f"<br>Path hops: {_number(metrics.get('hops'))}<extra></extra>")
        for xs, ys in (([x1, xm], [y1, ym]), ([xm, x4], [ym, y4])):
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=width, dash=dash),
                                     hovertemplate=hover, showlegend=False))
    statuses = {
        1: "Source · fresh route event" if routing_fresh else "Source · no fresh event",
        2: "Active relay" if selected == 2 else "Candidate relay",
        3: "Active relay" if selected == 3 else "Candidate relay",
        4: "Gateway · fresh telemetry" if gateway_fresh else "Gateway · no fresh telemetry",
    }
    if event and not routing_fresh:
        statuses[2] = statuses[3] = "Historical route evidence"
    node_colors = {1: "#74a8ff", 2: "#39d7bd" if selected == 2 and routing_fresh else "#afbed0",
                   3: "#39d7bd" if selected == 3 and routing_fresh else "#afbed0",
                   4: "#39d7bd" if gateway_fresh else "#78879a"}
    fig.add_trace(go.Scatter(
        x=[positions[node][0] for node in positions], y=[positions[node][1] for node in positions],
        mode="markers+text", text=[f"ESP32_{node:02d}" for node in positions], textposition="bottom center",
        marker=dict(size=34, color=[node_colors[node] for node in positions], line=dict(color="#d9e7f5", width=1)),
        customdata=[[statuses[node], sensor.get("rssiDbm", "N/A") if node == 4 and sensor else "N/A"] for node in positions],
        hovertemplate="%{text}<br>%{customdata[0]}<br>Last-hop RSSI: %{customdata[1]} dBm<extra></extra>",
        showlegend=False))
    fig.update_layout(template="plotly_dark", height=340, margin=dict(l=10, r=10, t=18, b=20),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(visible=False, range=[-0.02, 1.02]), yaxis=dict(visible=False, range=[0, 1]),
                      hoverlabel=dict(bgcolor="#142033", font_color="#e6edf7"))
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    st.caption("Teal = selected active route · blue-gray = measured available alternative · red dashed = reported unavailable · dotted gray = unknown or stale evidence.")

st.set_page_config(page_title="P12-IOT Live Routing Monitor", page_icon="📡", layout="wide")
st.markdown("""
<style>
.stApp{background:#0a101c;color:#e6edf7}
.block-container{padding-top:1.35rem;padding-bottom:2.5rem;max-width:1600px}
[data-testid='stMetric']{background:#111b2a;border:1px solid #26364a;padding:14px 16px;border-radius:10px}
[data-testid='stMetricLabel']{color:#9aabc0}
[data-testid='stMetricValue']{font-size:1.45rem}
section[data-testid='stSidebar']{background:#0d1624;border-right:1px solid #1f2b3a}
.p12-brand{font-size:1.15rem;font-weight:750;letter-spacing:.12em;color:#e8f0fb}
.p12-kicker{color:#43d9c0;font-size:.73rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase}
.p12-subtle{color:#93a4b8;font-size:.88rem}
div[data-testid='stPlotlyChart']{border:1px solid #1f2b3a;border-radius:10px;background:#0e1724;padding:4px}
hr{border-color:#233247}
</style>
""", unsafe_allow_html=True)
with st.sidebar:
    st.markdown('<div class="p12-brand">P12-IOT</div><div class="p12-subtle">NETWORK OPERATIONS</div>', unsafe_allow_html=True)
    st.markdown("**P12-MESH-01** · 4 ESP32 nodes")
    st.markdown("#### Navigation")
    st.markdown("[Overview](#network-overview)  ·  [Topology](#mesh-topology)  ·  [Control](#autonomous-control)  ·  [Analytics](#network-performance)  ·  [ML routing](#ml-routing-intelligence)  ·  [Sensors](#sensor-monitoring)  ·  [Events](#routing-event-explorer)")
    refresh_interval = st.selectbox("Refresh interval", (5, 10, 15, 30), index=0, format_func=lambda seconds: f"{seconds} seconds", key="p12_refresh_interval")
    auto_refresh_enabled = st.toggle("Live refresh", value=True, key="p12_auto_refresh")

st.markdown('<div class="p12-kicker">ESP32 mesh · live observability</div>', unsafe_allow_html=True)
st.title("P12-IOT LIVE ROUTING MONITOR")
st.caption("Real-time network observability and autonomous ML-based routing optimization.")

@st.fragment(run_every=f"{refresh_interval}s" if auto_refresh_enabled else None)
def _render_live_p12():
    st.caption(f"P12 sensor + routing APIs · hardware older than {P12_STALE_AFTER_SECONDS}s marked historical")
    control_token = _p12_api_token()
    controller_policy_ready = configured_route_policy() is not None
    control_state = None
    control_error = None
    if control_token:
        try:
            control_state = _p12_control_request("GET", P12_CONTROL_API_URL, control_token)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            control_error = f"Routing control API unavailable: {_p12_request_error(exc)}"
    else:
        control_error = "P12_IOT_INGEST_TOKEN is not configured; autonomous control unavailable."
    if control_state:
        if "p12_auto_toggle" not in st.session_state:
            st.session_state.p12_auto_toggle = control_state["enabled"] is True
        requested_enabled = st.toggle("Autonomous ML control", key="p12_auto_toggle")
        if requested_enabled != (control_state.get("enabled") is True):
            try:
                control_state = _p12_control_request(
                    "PUT", P12_CONTROL_API_URL, control_token,
                    {"enabled": requested_enabled, "expectedEpoch": control_state["epoch"]},
                )
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                control_error = f"Could not change autonomous control state: {_p12_request_error(exc)}"
                control_state = None
        if control_state and controller_policy_ready:
            try:
                control_state = _p12_control_request(
                    "POST", f"{P12_CONTROL_API_URL}/heartbeat", control_token,
                    {"epoch": control_state["epoch"]},
                )
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                control_error = f"ML controller heartbeat failed: {_p12_request_error(exc)}"
                control_state = None
    else:
        st.toggle("Autonomous ML control", value=False, disabled=True, key="p12_auto_toggle_unavailable")
    st.session_state.p12_control_state = control_state
    st.session_state.p12_control_error = control_error
    st.session_state.p12_auth_configured = bool(control_token)
    if control_state:
        effective_owner = control_state.get("enabled") is True and control_state.get("controllerAvailable") is True
        device_synced = (control_state.get("deviceEpoch") == control_state.get("epoch")
                         and control_state.get("deviceEnabled") is effective_owner)
        device_owner = control_state.get("deviceEnabled")
        device_label = "ENABLED" if device_owner is True else "DISABLED" if device_owner is False else "UNKNOWN"
        controller_label = ("READY" if controller_policy_ready and control_state.get("controllerAvailable")
                            else "NOT CALIBRATED" if not controller_policy_ready else "LEASE EXPIRED")
    live_limit = st.selectbox("History window", (10, 25, 50, 100), index=1, key="p12_live_limit")
    refresh_now = st.button("Refresh now", key="p12_live_refresh", type="primary")
    if refresh_now or auto_refresh_enabled:
        st.session_state.p12_last_attempt_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            request = Request(f"{P12_API_URL}?limit={live_limit}", headers={"User-Agent": "P12-IOT-Streamlit/2.0"})
            with urlopen(request, timeout=10) as response:
                sensor_rows = json.loads(response.read())
            sensor_rows = parse_sensor_response(sensor_rows)
            st.session_state.p12_live_readings = merge_incremental_records(
                st.session_state.get("p12_live_readings", []), sensor_rows, live_limit
            )
            st.session_state.p12_live_error = None
            st.session_state.p12_sensor_connected = True
        except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            st.session_state.p12_live_error = f"Sensor API request failed: {exc}"
            st.session_state.p12_sensor_connected = False
        try:
            request = Request(f"{P12_ROUTING_API_URL}?limit={live_limit}", headers={"User-Agent": "P12-IOT-Streamlit/2.0"})
            with urlopen(request, timeout=10) as response:
                routing_payload = json.loads(response.read())
            routing_payload = parse_routing_response(routing_payload)
            routing_payload["events"] = merge_incremental_records(
                st.session_state.get("p12_routing_events", []), routing_payload["events"], live_limit
            )
            st.session_state.p12_routing_summary = routing_payload
            st.session_state.p12_routing_error = None
            st.session_state.p12_routing_connected = True
        except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            st.session_state.p12_routing_error = f"Routing API request failed: {exc}"
            st.session_state.p12_routing_connected = False
        if st.session_state.get("p12_sensor_connected") and st.session_state.get("p12_routing_connected"):
            st.session_state.p12_live_fetched_at = st.session_state.p12_last_attempt_at

    fetched = st.session_state.get("p12_live_fetched_at")
    sensor_state = st.session_state.get("p12_sensor_connected")
    routing_state = st.session_state.get("p12_routing_connected")
    status_cols = st.columns(3)
    status_cols[0].metric("Sensor API", "Connected" if sensor_state else "Unavailable" if sensor_state is False else "Not checked")
    status_cols[1].metric("Routing API", "Connected" if routing_state else "Unavailable" if routing_state is False else "Not checked")
    status_cols[2].metric("Last successful refresh", fetched or "N/A")
    if st.session_state.get("p12_live_error"):
        st.error(st.session_state.p12_live_error)
    if st.session_state.get("p12_routing_error"):
        st.warning(st.session_state.p12_routing_error)

    readings = st.session_state.get("p12_live_readings", [])
    events = st.session_state.get("p12_routing_events", [])
    readings = [row for row in readings if isinstance(row, dict)]
    events = [row for row in events if isinstance(row, dict)]
    hardware_rows = hardware_records(readings)
    latest_sensor = max(hardware_rows, key=lambda row: parse_timestamp(row.get("receivedAt")) or datetime.min.replace(tzinfo=timezone.utc), default=None)
    latest_event = max(events, key=lambda row: parse_timestamp(row.get("receivedAt")) or datetime.min.replace(tzinfo=timezone.utc), default=None)
    now_utc = datetime.now(timezone.utc)
    sensor_time = parse_timestamp((latest_sensor or {}).get("receivedAt"))
    sensor_age = (now_utc - sensor_time).total_seconds() if sensor_time else None
    sensor_fresh = record_is_fresh(latest_sensor, now_utc, P12_STALE_AFTER_SECONDS)
    routing_fresh = record_is_fresh(latest_event, now_utc, P12_STALE_AFTER_SECONDS)
    if sensor_fresh:
        st.success(f"LIVE HARDWARE DATA · freshest gateway-persisted sample {sensor_time.isoformat(timespec='seconds')}")
    elif latest_sensor:
        st.warning(f"HISTORICAL HARDWARE DATA · stale by {_number(sensor_age, 's', 0)}; latest persisted sample {sensor_time.isoformat(timespec='seconds') if sensor_time else 'N/A'}")
    else:
        st.info("No persisted live_hardware sensor record loaded. Hardware readings unavailable.")
    if any(row.get("provenance") == "api_validation" for row in readings):
        st.caption("API validation records are excluded from hardware metrics.")
    if fetched:
        st.caption(f"Dashboard fetch timestamp: {fetched} UTC · device event timestamps and sequence values are preserved below.")
    if latest_event and not routing_fresh:
        st.warning("Routing event data is stale. The last persisted decision is historical and does not establish the current active route.")

    st.markdown('<div id="network-overview"></div>', unsafe_allow_html=True)
    st.markdown("### Network overview")
    if sensor_fresh and latest_sensor:
        gateway_status = "Online · fresh telemetry"
    elif latest_sensor:
        gateway_status = "Stale · no recent telemetry"
    else:
        gateway_status = "Unavailable · API unavailable" if sensor_state is False else "Unavailable · no hardware telemetry"
    mode_value = latest_event.get("routingMode", "N/A") if latest_event and routing_fresh else "STALE / N/A"
    observed_nodes = set()
    for row in events:
        for key in ("sourceNodeId", "currentNodeId", "selectedNextHopId", "forwardingNodeId"):
            if isinstance(row.get(key), int):
                observed_nodes.add(row[key])
    if sensor_fresh:
        observed_nodes.add(4)
    summary = st.session_state.get("p12_routing_summary", {})
    total_received = summary.get("totalGatewayReceived") if isinstance(summary, dict) else None
    interval_stats = delivery_intervals(events)
    window_attempts = sum(item["attempts"] for item in interval_stats)
    window_pdr = (sum(item["delivered"] for item in interval_stats) / window_attempts) if window_attempts else None
    active_hop_value = latest_event.get("selectedNextHopId") if latest_event and routing_fresh else None
    delivered_cols = st.columns(4)
    delivered_cols[0].metric("Gateway", gateway_status)
    delivered_cols[1].metric("Observed nodes", str(len(observed_nodes)) if observed_nodes else "N/A")
    delivered_cols[2].metric("Routing mode", mode_value)
    delivered_cols[3].metric("Active next hop", f"ESP32_{active_hop_value}" if active_hop_value in (2, 3) else "N/A")
    delivered_cols = st.columns(4)
    delivered_cols[0].metric("Packet delivery ratio", f"{window_pdr:.1%}" if window_pdr is not None else "N/A")
    delivered_cols[1].metric("Measured packet loss", f"{1-window_pdr:.1%}" if window_pdr is not None else "N/A")
    delivered_cols[2].metric("Gateway-received packets", str(total_received) if isinstance(total_received, int) and not isinstance(total_received, bool) else "N/A")
    delivered_cols[3].metric("Last telemetry", latest_sensor.get("receivedAt", "N/A") if latest_sensor else "N/A")
    if latest_sensor:
        st.caption(f"Last telemetry: {latest_sensor.get('receivedAt', 'N/A')} · {'fresh' if sensor_fresh else 'historical'}")
    if latest_event:
        st.caption(f"Last routing event: {latest_event.get('receivedAt', 'N/A')} · {'fresh' if routing_fresh else 'historical'}")
    if not interval_stats:
        st.caption("PDR is N/A until at least two gateway-confirmed events provide a sent-counter interval.")

    st.markdown('<div id="autonomous-control"></div>', unsafe_allow_html=True)
    st.markdown("### Autonomous control")
    control_cols = st.columns(5)
    if control_state:
        control_cols[0].metric("Worker desired state", "Enabled" if control_state.get("enabled") is True else "Disabled")
        control_cols[1].metric("Routing owner", "Python ML" if effective_owner else "Embedded fallback")
        control_cols[2].metric("Device-reported state", device_label)
        control_cols[3].metric("Controller heartbeat", "Healthy" if control_state.get("controllerAvailable") else "Expired / unavailable")
        control_cols[4].metric("Control epoch", str(control_state.get("epoch", "N/A")))
        st.caption(f"Heartbeat: {control_state.get('controllerHeartbeatAt', 'N/A')} · gateway lease: {control_state.get('leaseExpiresAt', 'N/A')} · synchronization: {'in sync' if device_synced else 'pending / mismatch'}")
        if not device_synced:
            st.warning("Device ownership does not match Worker desired state. Routing commands remain gated.")
    else:
        for col, label in zip(control_cols, ("Worker state", "Routing owner", "Device state", "Heartbeat", "Control epoch")):
            col.metric(label, "Unavailable")
    if not control_token:
        st.warning("Authentication token missing. Autonomous control is unavailable.")
    if not controller_policy_ready:
        st.warning("Validated route calibration is not configured. Python ML remains shadow-only; embedded routing stays in control.")
    if not sensor_fresh:
        st.warning("Telemetry is stale or unavailable. New routing commands are withheld.")
    if control_error:
        st.warning(control_error)

    st.markdown('<div id="mesh-topology"></div>', unsafe_allow_html=True)
    st.markdown("### Mesh topology")
    _render_topology(latest_event, routing_fresh, sensor_fresh, latest_sensor)

    st.markdown('<div id="sensor-monitoring"></div>', unsafe_allow_html=True)
    st.markdown("### Sensor monitoring")
    if latest_sensor:
        sensor_cols = st.columns(5)
        sensor_cols[0].metric("Temperature", _number(latest_sensor.get("temperatureC"), " °C"))
        sensor_cols[1].metric("Humidity", _number(latest_sensor.get("humidityPercent"), "%"))
        sensor_cols[2].metric("Light sensor", {0: "Inactive", 1: "Active", None: "N/A"}.get(latest_sensor.get("lightStatus"), "N/A"))
        sound = latest_sensor.get("soundDetected")
        sensor_cols[3].metric("Sound", "Detected" if sound is True else "Not detected" if sound is False else "N/A")
        sensor_cols[4].metric("RSSI", _number(latest_sensor.get("rssiDbm"), " dBm", 0))
        st.caption(f"Sequence {latest_sensor.get('sequence', 'N/A')} · source ESP32_{latest_sensor.get('sourceNodeId', 'N/A')} · received {latest_sensor.get('receivedAt', 'N/A')} · { 'fresh' if sensor_fresh else 'stale/historical' }")
    else:
        st.info("Temperature, humidity, light and sound: N/A")

    st.markdown('<div id="ml-routing-intelligence"></div>', unsafe_allow_html=True)
    st.markdown("### ML routing intelligence")
    if latest_event:
        configured_policy = configured_route_policy()
        policy = configured_policy or RoutePolicy(None, None, None, None, P12_STALE_AFTER_SECONDS)
        active_hop = latest_event.get("selectedNextHopId")
        evidence_key = tuple(latest_event.get(key) for key in
                             ("sourceNodeId", "experimentId", "sequence", "sourceUptimeMs"))
        route_change_times = [parse_timestamp(row.get("receivedAt")) for row in events
                              if row.get("routeChanged") is True]
        route_change_times = [value for value in route_change_times if value is not None]
        last_route_change_at = max(route_change_times, default=None)
        model = _p12_route_model()
        candidate_check = evaluate_live_route(
            latest_event, model=model, policy=policy, active_next_hop=active_hop,
            now=now_utc, last_route_change_at=last_route_change_at, repeated_candidate_count=1,
        )
        candidate_signature = None
        if (candidate_check.get("nextHopId") != active_hop and candidate_check.get("reason") in
                ("hysteresis_not_satisfied", "minimum_change_interval", "policy_gates_satisfied")):
            candidate_signature = (active_hop, candidate_check.get("nextHopId"),
                                   candidate_check.get("modelVersion"),
                                   control_state.get("epoch") if control_state else None)
        signature, repeat_count, last_evidence = advance_hysteresis(
            st.session_state.get("p12_hysteresis_signature"),
            st.session_state.get("p12_hysteresis_count", 0),
            st.session_state.get("p12_hysteresis_evidence"),
            candidate_signature, evidence_key, candidate_signature is not None,
        )
        st.session_state.p12_hysteresis_signature = signature
        st.session_state.p12_hysteresis_count = repeat_count
        st.session_state.p12_hysteresis_evidence = last_evidence
        shadow = evaluate_live_route(
            latest_event, model=model, policy=policy, active_next_hop=active_hop,
            now=now_utc, last_route_change_at=last_route_change_at,
            repeated_candidate_count=repeat_count,
        )
        st.markdown("**Python route-model recommendation · shadow inference**")
        recommendation_cols = st.columns(5)
        recommendation_cols[0].metric("Predicted class", str(shadow.get("prediction", "N/A")))
        recommendation_cols[1].metric("Recommended hop", f"ESP32_{shadow['nextHopId']}" if shadow.get("nextHopId") in (2, 3) else "N/A")
        recommendation_cols[2].metric("Confidence", _percentage(shadow.get("confidence")))
        recommendation_cols[3].metric("Estimated improvement", _percentage(shadow.get("improvement")))
        recommendation_cols[4].metric("Inference", shadow.get("decision", "N/A"))
        st.caption(f"Model {shadow.get('modelVersion', 'N/A')} · reason: {shadow.get('reason', 'N/A')} · decision time: {latest_event.get('receivedAt', 'N/A')}")
        st.caption("Inference uses fresh gateway route-event features. Commands require enabled Worker ownership and validated calibration; otherwise inference remains shadow-only.")
        event_time = parse_timestamp(latest_event.get("receivedAt"))
        decision_for_log = dict(shadow)
        if control_state and control_state.get("enabled") is not True and shadow.get("decision") == "ELIGIBLE":
            decision_for_log.update(decision="HOLD", reason="autonomous_control_disabled")
        if event_time and control_token:
            decision_identity = ":".join(str(value) for value in (
                latest_event.get("sourceNodeId"), latest_event.get("experimentId"),
                latest_event.get("sequence"), latest_event.get("sourceUptimeMs"),
                control_state.get("epoch") if control_state else None,
                configured_policy.confidence_min if configured_policy else None,
                configured_policy.improvement_min if configured_policy else None,
                decision_for_log.get("decision"), decision_for_log.get("reason"),
            ))
            log_payload = {
                "decisionId": str(uuid5(NAMESPACE_URL, f"P12-IOT:decision:{decision_identity}")),
                "networkId": "P12-MESH-01", "sourceNodeId": 1,
                "evidenceSequence": latest_event.get("sequence", 0),
                "controlEpoch": control_state.get("epoch") if control_state else None,
                "modelVersion": shadow.get("modelVersion", "decision-tree-v1-seed-20261101"),
                "predictedClass": shadow.get("prediction"), "confidence": shadow.get("confidence"),
                "activeNextHopId": latest_event.get("selectedNextHopId"),
                "candidateNextHopId": shadow.get("nextHopId"), "improvement": shadow.get("improvement"),
                "decision": decision_for_log.get("decision", "HOLD"),
                "reason": decision_for_log.get("reason", "unknown"), "observedAt": event_time.isoformat(),
            }
            try:
                _p12_control_request("POST", "https://api.craftiq.in/p12/routing-decisions", control_token, log_payload)
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                st.session_state.p12_decision_log_error = f"Decision persistence failed: {_p12_request_error(exc)}"
        if st.session_state.get("p12_decision_log_error"):
            st.warning(st.session_state.p12_decision_log_error)
        latest_command = st.session_state.get("p12_last_ml_command")
        if latest_command and control_token:
            try:
                latest_command = _p12_control_request(
                    "GET", f"{P12_COMMANDS_API_URL}/{latest_command['commandId']}", control_token,
                )
                st.session_state.p12_last_ml_command = latest_command
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                st.session_state.p12_command_status_error = f"Command status refresh failed: {_p12_request_error(exc)}"
        effective_owner = bool(control_state and control_state.get("enabled") is True
                               and control_state.get("controllerAvailable") is True)
        device_synced = bool(control_state and control_state.get("deviceEpoch") == control_state.get("epoch")
                             and control_state.get("deviceEnabled") is effective_owner)
        if (control_state and device_synced and control_state.get("enabled") is True and configured_policy
                and shadow.get("decision") == "ELIGIBLE" and control_token
                and not (latest_command and latest_command.get("status") == "PENDING")):
            expiry = event_time.timestamp() + 50 if event_time else 0
            expiry_dt = datetime.fromtimestamp(expiry, timezone.utc) if expiry else None
            if expiry_dt and expiry_dt > now_utc:
                identity = ":".join(str(value) for value in (
                    control_state["epoch"], latest_event.get("sourceNodeId"),
                    latest_event.get("sequence"), latest_event.get("selectedNextHopId"),
                    shadow.get("nextHopId"), shadow.get("modelVersion"),
                ))
                command_id = str(uuid5(NAMESPACE_URL, f"P12-IOT:{identity}"))
                command = {
                    "commandId": command_id, "controlEpoch": control_state["epoch"],
                    "sourceNodeId": 1, "expectedNextHopId": latest_event.get("selectedNextHopId"),
                    "requestedNextHopId": shadow.get("nextHopId"),
                    "evidenceSequence": latest_event.get("sequence"),
                    "expiresAt": expiry_dt.isoformat(), "policyVersion": shadow.get("modelVersion"),
                }
                try:
                    command_status = _p12_control_request("POST", P12_COMMANDS_API_URL, control_token, command)
                    st.session_state.p12_last_ml_command = command_status
                except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                    st.session_state.p12_command_error = f"ML command submission failed: {_p12_request_error(exc)}"
            else:
                st.session_state.p12_command_error = "ML command withheld: telemetry evidence is too close to expiry."
        latest_command = st.session_state.get("p12_last_ml_command")
        if latest_command and control_token:
            try:
                latest_command = _p12_control_request(
                    "GET", f"{P12_COMMANDS_API_URL}/{latest_command['commandId']}", control_token,
                )
                st.session_state.p12_last_ml_command = latest_command
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                st.session_state.p12_command_status_error = f"Command status refresh failed: {_p12_request_error(exc)}"
        if latest_command:
            lifecycle = st.columns(4)
            lifecycle[0].metric("Command status", latest_command.get("status", "N/A"))
            lifecycle[1].metric("Gateway delivery", latest_command.get("deliveredAt", "N/A"))
            lifecycle[2].metric("Device result / ACK", latest_command.get("result", "N/A"))
            applied_hop = latest_command.get("appliedNextHopId")
            lifecycle[3].metric("Device-reported applied hop", f"ESP32_{applied_hop}" if applied_hop in (2, 3) else "N/A")
            st.caption(f"Command {latest_command.get('commandId')} · expected route change {latest_command.get('expectedNextHopId', 'N/A')} → {latest_command.get('requestedNextHopId', 'N/A')}")
            if str(latest_command.get("status", "")).upper() in ("FAILED", "REJECTED", "EXPIRED"):
                st.warning(f"Route command {latest_command.get('status', '').lower()}: {latest_command.get('result', 'device result unavailable')}")
            feedback = compare_route_performance(
                events, parse_timestamp(latest_command.get("executedAt")),
                latest_command.get("expectedNextHopId"), latest_command.get("requestedNextHopId"),
            )
            st.markdown(f"**Forwarding verification:** {feedback.get('status', 'N/A')} · {feedback.get('reason', feedback.get('limitation', ''))}")
        if st.session_state.get("p12_command_status_error"):
            st.warning(st.session_state.p12_command_status_error)
        if st.session_state.get("p12_command_error"):
            st.warning(st.session_state.p12_command_error)
        decision_cols = st.columns(5)
        decision_cols[0].metric("Prediction", str(latest_event.get("predictedClass", "N/A")))
        decision_cols[1].metric("Selected next hop", f"ESP32_{latest_event.get('selectedNextHopId')}" if latest_event.get("selectedNextHopId") is not None else "N/A")
        decision_cols[2].metric("Mode", latest_event.get("routingMode", "N/A") if routing_fresh else "STALE / N/A")
        decision_cols[3].metric("Forwarding result", latest_event.get("forwardingResult", "N/A"))
        decision_cols[4].metric("ML inputs", "Valid" if latest_event.get("featureValid") is True else "UNAVAILABLE")
        prior_event = next((row for row in sorted(events, key=lambda item: parse_timestamp(item.get("receivedAt")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
                            if row is not latest_event and row.get("selectedNextHopId") is not None), None)
        st.caption(f"Previous observed next hop: ESP32_{prior_event.get('selectedNextHopId')}" if prior_event else "Previous observed next hop: N/A")
        st.caption(f"ACK result: {latest_event.get('ackResult', 'N/A')} · sequence {latest_event.get('sequence', 'N/A')} · source uptime {latest_event.get('sourceUptimeMs', 'N/A')} ms · hop count {latest_event.get('hopCount', 'N/A')}")
        path_cols = st.columns(2)
        for col, title, key in ((path_cols[0], "Upper path · ESP32_02", "candidateUpper"), (path_cols[1], "Lower path · ESP32_03", "candidateLower")):
            path = latest_event.get(key) if isinstance(latest_event.get(key), dict) else {}
            col.markdown(f"**{title}**")
            col.write(f"Available: {path.get('available', 'N/A')} · PDR: {_percentage(path.get('pdr'))} · latency: {_number(path.get('latencyMs'), ' ms')} · hops: {_number(path.get('hops'))}")
        feature_names = ["upper_available", "upper_pdr_estimate", "upper_latency_ms", "upper_hops", "lower_available", "lower_pdr_estimate", "lower_latency_ms", "lower_hops"]
        feature_values = latest_event.get("modelFeatures")
        st.dataframe(pd.DataFrame({"Model feature (Step 2 order)": feature_names, "Measured value": feature_values if isinstance(feature_values, list) and len(feature_values) == 8 else ["N/A"] * 8}), width="stretch", hide_index=True)
        if routing_fresh and latest_event.get("routingMode") == "ML_ACTIVE" and latest_event.get("forwardingResult") == "GATEWAY_RECEIVED":
            st.success("Firmware reports ML_ACTIVE; selected route forwarded packet to Gateway. This confirms this packet only.")
        elif routing_fresh and latest_event.get("routingMode") == "BASELINE_FALLBACK":
            st.info("BASELINE_FALLBACK · model inputs were unavailable or model output did not control forwarding.")
        elif not routing_fresh:
            st.caption(f"Historical mode: {latest_event.get('routingMode', 'N/A')} · forwarding result {latest_event.get('forwardingResult', 'N/A')}")
    else:
        st.info("No routing events available. Prediction, candidate metrics and forwarding outcomes are N/A.")

    st.markdown('<div id="network-performance"></div>', unsafe_allow_html=True)
    st.markdown("### Network performance")
    if interval_stats:
        perf = pd.DataFrame(interval_stats)
        perf["timestamp"] = pd.to_datetime(perf["timestamp"], utc=True, errors="coerce")
        perf = perf.dropna(subset=["timestamp"])
        left, right = st.columns(2)
        pdr_fig = go.Figure(go.Scatter(x=perf["timestamp"], y=perf["pdr"] * 100, mode="lines+markers", name="PDR %", connectgaps=False))
        pdr_fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", title="Measured delivery ratio by sent-counter interval", xaxis_title="Time (UTC)", yaxis_title="PDR (%)", height=300, margin=dict(l=10,r=10,t=40,b=10), xaxis=dict(rangeselector=dict(buttons=[dict(count=1,label="1h",step="hour",stepmode="backward"),dict(count=6,label="6h",step="hour",stepmode="backward"),dict(step="all",label="All")]), type="date"))
        left.plotly_chart(pdr_fig, width="stretch")
        loss_fig = go.Figure(go.Scatter(x=perf["timestamp"], y=perf["loss"] * 100, mode="lines+markers", name="Packet loss %", line=dict(color="#ed6b78"), connectgaps=False))
        loss_fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", title="Measured packet loss by sent-counter interval", xaxis_title="Time (UTC)", yaxis_title="Loss (%)", height=300, margin=dict(l=10,r=10,t=40,b=10), xaxis=dict(rangeselector=dict(buttons=[dict(count=1,label="1h",step="hour",stepmode="backward"),dict(count=6,label="6h",step="hour",stepmode="backward"),dict(step="all",label="All")]), type="date"))
        right.plotly_chart(loss_fig, width="stretch")
    else:
        st.info("PDR/loss graph: N/A until an interval between confirmed routing events is available.")
    def plot_history(title, records, timestamp_key, value_key, axis_title, suffix=""):
        points = timestamped_values(records, value_key, timestamp_key)
        if not points:
            st.info(f"{title}: no measured values available.")
            return
        fig = go.Figure(go.Scatter(
            x=[point[0] for point in points], y=[point[1] for point in points],
            customdata=[point[2] for point in points], mode="lines+markers",
            connectgaps=False, hovertemplate=f"%{{x}}<br>%{{y}}{suffix}<br>sequence %{{customdata}}<extra></extra>"))
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          title=title, xaxis_title="Received time (UTC)", yaxis_title=axis_title,
                          height=290, margin=dict(l=10, r=10, t=42, b=10),
                          xaxis=dict(rangeselector=dict(buttons=[dict(count=1,label="1h",step="hour",stepmode="backward"),dict(count=6,label="6h",step="hour",stepmode="backward"),dict(step="all",label="All")]), type="date"),
                          hoverlabel=dict(bgcolor="#142033", font_color="#e6edf7"))
        st.plotly_chart(fig, width="stretch")

    sensor_cols = st.columns(2)
    with sensor_cols[0]:
        plot_history("Temperature · ESP32_01", hardware_rows, "receivedAt", "temperatureC", "Temperature (°C)")
    with sensor_cols[1]:
        plot_history("Humidity · ESP32_01", hardware_rows, "receivedAt", "humidityPercent", "Humidity (%)")
    with sensor_cols[0]:
        plot_history("RSSI · ESP32_01", hardware_rows, "receivedAt", "rssiDbm", "RSSI (dBm)")
    latency_rows = []
    for event in events:
        latency_rows.append({"receivedAt": event.get("receivedAt"), "sequence": event.get("sequence"),
                             "latencyMs": event.get("latencyMs")})
    with sensor_cols[1]:
        plot_history("Selected-route latency estimate", latency_rows, "receivedAt", "latencyMs", "Estimated route latency (ms)")
    if events:
        changes = [row for row in events if row.get("routeChanged") is True and parse_timestamp(row.get("receivedAt"))]
        if changes:
            route_fig = go.Figure(go.Scatter(x=[parse_timestamp(row["receivedAt"]) for row in changes],
                y=list(range(1, len(changes) + 1)), mode="markers+lines",
                customdata=[row.get("sequence") for row in changes],
                hovertemplate="%{x}<br>route change %{y}<br>sequence %{customdata}<extra></extra>"))
            route_fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", title="Routing changes", xaxis_title="Received time (UTC)", yaxis_title="Cumulative changes", height=290, xaxis=dict(rangeselector=dict(buttons=[dict(count=1,label="1h",step="hour",stepmode="backward"),dict(count=6,label="6h",step="hour",stepmode="backward"),dict(step="all",label="All")]), type="date"))
            st.plotly_chart(route_fig, width="stretch")
        path_rows = []
        for row in events:
            timestamp = parse_timestamp(row.get("receivedAt"))
            if not timestamp:
                continue
            for label, key in (("Upper", "candidateUpper"), ("Lower", "candidateLower")):
                candidate = row.get(key)
                if isinstance(candidate, dict):
                    path_rows.append((timestamp, label, candidate.get("pdr"), candidate.get("latencyMs"), row.get("sequence")))
        valid_paths = [item for item in path_rows if isinstance(item[2], (int, float)) and not isinstance(item[2], bool)]
        if valid_paths:
            path_fig = go.Figure()
            for label in ("Upper", "Lower"):
                series = sorted((item for item in valid_paths if item[1] == label), key=lambda item: item[0])
                path_fig.add_trace(go.Scatter(x=[item[0] for item in series], y=[item[2] * 100 for item in series],
                    customdata=[[item[3], item[4]] for item in series], name=f"{label} path PDR",
                    mode="lines+markers", connectgaps=False,
                    hovertemplate="%{x}<br>PDR %{y:.1f}%<br>latency %{customdata[0]} ms<br>sequence %{customdata[1]}<extra></extra>"))
            path_fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", title="Upper vs lower path performance", xaxis_title="Received time (UTC)", yaxis_title="Measured candidate PDR (%)", height=310, xaxis=dict(rangeselector=dict(buttons=[dict(count=1,label="1h",step="hour",stepmode="backward"),dict(count=6,label="6h",step="hour",stepmode="backward"),dict(step="all",label="All")]), type="date"))
            st.plotly_chart(path_fig, width="stretch")
        else:
            st.info("Upper/lower path comparison: no candidate PDR measurements available.")
    performance_cols = st.columns(4)
    performance_cols[0].metric("End-to-end latency", "N/A · not measured in API contract")
    performance_cols[1].metric("Route changes", str(sum(row.get("routeChanged") is True for row in events)) if events else "N/A")
    performance_cols[2].metric("Gateway-confirmed transmissions", str(sum(row.get("forwardingResult") == "GATEWAY_RECEIVED" for row in events)) if events else "N/A")
    performance_cols[3].metric("Failed transmissions", "N/A · failed packets cannot reach this Gateway event API")

    st.markdown('<div id="routing-event-explorer"></div>', unsafe_allow_html=True)
    st.markdown("### Routing event explorer")
    if events:
        history = []
        for row in sorted(events, key=lambda item: parse_timestamp(item.get("receivedAt")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
            selected = row.get("selectedNextHopId")
            history.append({
                "Timestamp": row.get("observedAt") or row.get("receivedAt") or "N/A",
                "Sequence": row.get("sequence", "N/A"),
                "Source": f"ESP32_{row.get('sourceNodeId')}" if row.get("sourceNodeId") is not None else "N/A",
                "Selected route": f"ESP32_01 → ESP32_{selected} → ESP32_04" if selected is not None else "N/A",
                "Routing algorithm": row.get("routingAlgorithm", "N/A"),
                "Prediction": row.get("predictedClass", "N/A"),
                "Mode": row.get("routingMode", "N/A"),
                "Forwarding": row.get("forwardingResult", "N/A"),
                "Route-change reason": row.get("routeChangeReason", "N/A"),
                "ACK": row.get("ackResult", "N/A"),
                "Source uptime ms": row.get("sourceUptimeMs", "N/A"),
            })
        history_frame = pd.DataFrame(history)
        filter_cols = st.columns([2, 1, 1])
        search = filter_cols[0].text_input("Search events", placeholder="Node, route, reason…", key="p12_history_filter")
        mode_filter = filter_cols[1].selectbox("Routing mode", ["All", *sorted({str(row.get("routingMode", "N/A")) for row in events})], key="p12_mode_filter")
        result_filter = filter_cols[2].selectbox("Forwarding result", ["All", *sorted({str(row.get("forwardingResult", "N/A")) for row in events})], key="p12_result_filter")
        if search:
            mask = history_frame.astype(str).apply(lambda column: column.str.contains(search, case=False, regex=False)).any(axis=1)
            history_frame = history_frame[mask]
        if mode_filter != "All":
            history_frame = history_frame[history_frame["Mode"].astype(str) == mode_filter]
        if result_filter != "All":
            history_frame = history_frame[history_frame["Forwarding"].astype(str) == result_filter]
        st.dataframe(history_frame, width="stretch", hide_index=True)
        st.download_button("Export hardware routing CSV", history_frame.to_csv(index=False),
                           "p12_hardware_routing_history.csv", mime="text/csv")
    else:
        st.info("No routing history loaded. Refresh to query the P12-only event endpoint.")

    st.markdown("### Historical sensor records")
    if hardware_rows:
        st.dataframe(pd.DataFrame(hardware_rows), width="stretch", hide_index=True)
    else:
        st.caption("No historical hardware records are currently loaded.")
@st.fragment(run_every=f"{refresh_interval}s")
def _render_sidebar_status():
    control = st.session_state.get("p12_control_state")
    control_error = st.session_state.get("p12_control_error")
    sensor_connected = st.session_state.get("p12_sensor_connected")
    latest_sensor = max(
        hardware_records(st.session_state.get("p12_live_readings", [])),
        key=lambda row: parse_timestamp(row.get("receivedAt")) or datetime.min.replace(tzinfo=timezone.utc),
        default=None,
    )
    fresh = record_is_fresh(latest_sensor, datetime.now(timezone.utc), P12_STALE_AFTER_SECONDS)
    st.markdown("---")
    st.markdown("#### Gateway status")
    st.markdown(f"**{'ONLINE' if fresh else 'STALE' if latest_sensor else 'UNAVAILABLE'}**")
    st.caption("Fresh hardware telemetry" if fresh else "Historical telemetry" if latest_sensor else "No hardware telemetry loaded")
    st.markdown("#### Autonomous ML")
    if control:
        owner = "Python ML" if control.get("enabled") is True and control.get("controllerAvailable") is True else "Embedded fallback"
        state = "Enabled" if control.get("enabled") is True else "Disabled"
        st.markdown(f"**{state}** · owner: {owner}")
        st.caption(f"Epoch {control.get('epoch', 'N/A')} · controller {'healthy' if control.get('controllerAvailable') else 'expired/unavailable'}")
    elif not st.session_state.get("p12_auth_configured"):
        st.markdown("**Unavailable** · auth token missing")
    else:
        st.markdown("**Unavailable** · control API unavailable")
        if control_error:
            st.caption(control_error)
    st.markdown("#### Data refresh")
    st.caption(st.session_state.get("p12_live_fetched_at", "No successful refresh yet"))
    if sensor_connected is False or st.session_state.get("p12_routing_connected") is False:
        st.caption("One or more P12 APIs unavailable")


_render_live_p12()
with st.sidebar:
    _render_sidebar_status()
