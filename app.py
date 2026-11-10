import json
import os
from uuid import NAMESPACE_URL, uuid5
from datetime import datetime, timezone
import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from experiments.runner import SCENARIOS, run_suite
from ml.pipeline import train_model
from simulator.core import SimulationConfig, build_topology, run_simulation
from dashboard.p12_data import (
    delivery_intervals, format_metric, hardware_records, merge_incremental_records,
    parse_routing_response, parse_sensor_response,
    parse_timestamp, record_is_fresh,
)
from dashboard.autonomous import (
    RoutePolicy, advance_hysteresis, configured_route_policy,
    evaluate_live_route, load_route_model,
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

st.set_page_config(page_title="Intelligent IoT Mesh Routing", page_icon="📡", layout="wide")
st.title("Machine Learning-Based Intelligent Routing Optimization")
st.caption("SIMULATION DATA: reproducible synthetic runs. LIVE API DATA: read-only P12 endpoint. ML_ACTIVE is reserved for persisted live-hardware forwarding records.")

with st.sidebar:
    st.header("Scenario configuration")
    nodes = st.slider("Nodes", 6, 12, 6)
    packets = st.slider("Packets", 20, 500, 100, step=20)
    pps = st.slider("Packet rate (pps)", 1, 20, 5)
    loss = st.slider("Base link loss", 0.0, .6, .05, .01)
    latency = st.slider("Base latency (ms)", 1, 150, 20)
    rssi = st.slider("Simulated RSSI (dBm)", -100, -35, -60)
    capacity = st.slider("Link capacity (kbps)", 10, 1000, 250, step=10)
    load = st.slider("Traffic load", 0.0, 1.0, 0.0, .05)
    seed = st.number_input("Random seed", min_value=0, max_value=1_000_000, value=17)
    scenario = st.selectbox("Scenario", SCENARIOS)
    mode = st.radio("Routing mode", ["Compare both", "Minimum-hop baseline", "ML-assisted"])
    run = st.button("Run simulation", type="primary", width="stretch")
    exp_run = st.button("Run all scenarios (5 trials)", width="stretch")

if "latest" not in st.session_state:
    st.session_state.latest = None
if run:
    graph = build_topology(nodes, loss_probability=loss, latency_ms=latency,rssi_dbm=rssi,capacity_kbps=capacity)
    config = SimulationConfig(packet_count=packets, packet_rate_pps=pps, seed=int(seed),
                              scenario=scenario, traffic_load=load)
    with st.spinner("Training/loading synthetic model and simulating packets…"):
        model, eval_metrics, _ = train_model(seed=int(seed))
        algorithms = ["baseline", "ml"] if mode == "Compare both" else ["baseline" if mode.startswith("Minimum") else "ml"]
        results = {name:run_simulation(graph, config, name, model) for name in algorithms}
        st.session_state.latest = (results, eval_metrics)
if exp_run:
    with st.spinner("Running paired controlled trials…"):
        raw, aggregate = run_suite(trials=5, packets=packets, seed=int(seed), node_count=nodes)
        st.session_state.experiments = (raw, aggregate)

latest = st.session_state.latest
if latest is None:
    st.info("Configure a scenario, then run simulation. Initial topology contains two source-to-gateway corridors.")
    graph = build_topology(nodes, loss_probability=loss, latency_ms=latency,rssi_dbm=rssi,capacity_kbps=capacity)
else:
    results, eval_metrics = latest
    colset = st.columns(len(results))
    for col, (name, result) in zip(colset, results.items()):
        m=result["metrics"]
        col.metric(f"{name.title()} PDR", f"{m['pdr']*100:.1f}%")
        col.metric("Mean delivered latency", f"{m['mean_latency_ms']:.1f} ms" if pd.notna(m["mean_latency_ms"]) else "n/a")
        col.metric("Throughput", f"{m['throughput_kbps']:.3f} kbps")
    graph = next(iter(results.values()))["graph"]
highlight_route=set()
if latest:
    shown=results.get("ml",next(iter(results.values())))
    successful=shown["packets"][shown["packets"].delivered]
    if len(successful):
        route=successful.iloc[0].route.split("->")
        highlight_route={tuple(sorted(edge)) for edge in zip(route,route[1:])}

overview, topology_tab, events_tab, compare_tab, model_tab, live_p12_tab = st.tabs(["Overview", "Topology", "Packet events", "Performance", "Model evaluation", "Live P12 telemetry"])
with overview:
    st.subheader("Network summary")
    st.write(f"{graph.number_of_nodes()} nodes • {graph.number_of_edges()} links • source S • gateway G")
    st.write(f"Current scenario: **{scenario}** | routing: **{mode}** | seed: **{seed}**")
    st.caption("Latency covers delivered packets only. PDR = delivered/generated. Throughput = delivered payload bits / observation duration. Energy is not modeled.")
with topology_tab:
    pos = nx.spring_layout(graph, seed=17)
    fig = go.Figure()
    for a,b,d in graph.edges(data=True):
        state = d.get("available", True)
        selected=tuple(sorted((a,b))) in highlight_route
        fig.add_trace(go.Scatter(x=[pos[a][0],pos[b][0]], y=[pos[a][1],pos[b][1]], mode="lines",
            line=dict(color="#7c3aed" if selected and state else "#94a3b8" if state else "#ef4444", width=4 if selected else 2, dash="solid" if state else "dash"),
            hovertemplate=f"{a} ↔ {b}<br>RSSI {d['rssi_dbm']} dBm<br>loss {d['loss_probability']:.2f}<br>latency {d['latency_ms']} ms<extra></extra>", showlegend=False))
    colors=["#16a34a" if n=="G" else "#f97316" if n=="S" else "#2563eb" for n in graph.nodes]
    fig.add_trace(go.Scatter(x=[pos[n][0] for n in graph], y=[pos[n][1] for n in graph], mode="markers+text",
        text=list(graph.nodes), textposition="top center", marker=dict(size=28,color=colors), showlegend=False))
    fig.update_layout(height=540, margin=dict(l=10,r=10,t=10,b=10), xaxis=dict(visible=False), yaxis=dict(visible=False))
    st.plotly_chart(fig, width="stretch")
    st.caption("Green = gateway; orange = source; blue = relay; purple = first delivered route; red dashed = unavailable link. Link metrics are simulated.")
with events_tab:
    if latest:
        for name,result in results.items():
            st.subheader(name.title())
            ev=pd.DataFrame(result["events"])
            st.dataframe(ev, width="stretch", height=300)
            st.download_button(f"Download {name} packet CSV", result["packets"].to_csv(index=False), f"{name}_packets.csv", key=f"packets_{name}")
    else: st.info("Run a simulation to see actual forwarding and delivery events.")
with compare_tab:
    if latest:
        rows=[{"routing":k,**v["metrics"]} for k,v in results.items()]
        frame=pd.DataFrame(rows)
        st.dataframe(frame, width="stretch")
        chart=go.Figure()
        for metric,label in [("pdr","PDR"),("packet_loss_rate","Packet loss"),
                             ("mean_latency_ms","Mean latency ms"),("throughput_kbps","Throughput kbps"),
                             ("route_switch_count","Route switches")]:
            chart.add_bar(name=label,x=frame.routing,y=frame[metric])
        chart.update_layout(barmode="group",height=400)
        st.plotly_chart(chart,width="stretch")
        st.download_button("Download run metrics CSV",frame.to_csv(index=False),"simulation_metrics.csv")
    if "experiments" in st.session_state:
        raw,agg=st.session_state.experiments
        st.subheader("Paired scenario trials")
        st.dataframe(agg,width="stretch")
        st.download_button("Download trial results",raw.to_csv(index=False),"trial_results.csv")
        st.download_button("Download aggregate results",agg.to_csv(index=False),"aggregate_results.csv")
with model_tab:
    if latest:
        st.write({k:v for k,v in eval_metrics.items() if k not in ("train_runs","test_runs")})
        cm=eval_metrics["confusion_matrix"]
        st.write("Confusion matrix (rows actual [fail, success], columns predicted [fail, success])")
        st.dataframe(pd.DataFrame(cm,index=["actual fail","actual success"],columns=["pred fail","pred success"]))
    else: st.info("Model is trained on demand from synthetic simulated observations.")

@st.fragment(run_every="5s")
def _render_live_p12():
    st.subheader("P12-IOT live routing monitor")
    st.caption("LIVE HARDWARE DATA is read-only. SIMULATION DATA remains in the simulation tabs. Persisted records are historical after they become stale.")
    st.caption(f"Sensor API: {P12_API_URL} · Routing API: {P12_ROUTING_API_URL} · stale after {P12_STALE_AFTER_SECONDS}s")
    control_token = _p12_api_token()
    control_state = None
    control_error = None
    if control_token:
        try:
            control_state = _p12_control_request("GET", P12_CONTROL_API_URL, control_token)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            control_error = f"Routing control API unavailable: {exc}"
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
                control_error = f"Could not change autonomous control state: {exc}"
                control_state = None
    else:
        st.toggle("Autonomous ML control", value=False, disabled=True, key="p12_auto_toggle_unavailable")
    if control_state:
        device_synced = (control_state.get("deviceEpoch") == control_state.get("epoch")
                         and control_state.get("deviceEnabled") is control_state.get("enabled"))
        device_owner = control_state.get("deviceEnabled")
        device_label = "ENABLED" if device_owner is True else "DISABLED" if device_owner is False else "UNKNOWN"
        st.info(f"Worker desired state: {'ENABLED' if control_state['enabled'] else 'DISABLED'} · device owner: {device_label} · epoch {control_state['epoch']} · {'synced' if device_synced else 'transition pending'}")
    if control_error:
        st.warning(control_error)
    live_limit = st.selectbox("Recent records", (10, 25, 50, 100), index=1, key="p12_live_limit")
    auto_refresh = st.toggle("Auto-refresh every 5 seconds", value=True, key="p12_live_auto_refresh")
    refresh_now = st.button("Refresh P12 API data", key="p12_live_refresh", type="primary")
    if refresh_now or auto_refresh:
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
        st.session_state.p12_live_fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    fetched = st.session_state.get("p12_live_fetched_at")
    sensor_state = st.session_state.get("p12_sensor_connected")
    routing_state = st.session_state.get("p12_routing_connected")
    status_cols = st.columns(3)
    status_cols[0].metric("Sensor API", "Connected" if sensor_state else "Unavailable" if sensor_state is False else "Not checked")
    status_cols[1].metric("Routing API", "Connected" if routing_state else "Unavailable" if routing_state is False else "Not checked")
    status_cols[2].metric("Last API refresh", fetched or "N/A")
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
        st.info("No persisted live_hardware sensor record loaded. Simulation data is not shown in this section.")
    if any(row.get("provenance") == "api_validation" for row in readings):
        st.caption("API validation records are excluded from hardware metrics.")
    if fetched:
        st.caption(f"Dashboard fetch timestamp: {fetched} UTC · device event timestamps and sequence values are preserved below.")
    if latest_event and not routing_fresh:
        st.warning("Routing event data is stale. The last persisted decision is historical and does not establish the current active route.")

    st.markdown("### A. Network overview")
    if sensor_fresh and latest_sensor:
        gateway_status = "Online · fresh telemetry"
    elif latest_sensor:
        gateway_status = "Stale · no recent telemetry"
    else:
        gateway_status = "N/A · no hardware telemetry"
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
    delivered_cols = st.columns(5)
    delivered_cols[0].metric("Observed nodes", str(len(observed_nodes)) if observed_nodes else "N/A")
    delivered_cols[1].metric("Gateway", gateway_status)
    delivered_cols[2].metric("Active routing mode", mode_value)
    delivered_cols[3].metric("Packets received by Gateway", str(total_received) if isinstance(total_received, int) else "N/A")
    interval_stats = delivery_intervals(events)
    window_attempts = sum(item["attempts"] for item in interval_stats)
    window_pdr = (sum(item["delivered"] for item in interval_stats) / window_attempts) if window_attempts else None
    delivered_cols[4].metric("Measured delivery ratio", f"{window_pdr:.1%}" if window_pdr is not None else "N/A")
    if not interval_stats:
        st.caption("PDR is N/A until at least two gateway-confirmed events provide a sent-counter interval.")

    st.markdown("### B. Live sensor monitoring")
    if latest_sensor:
        sensor_cols = st.columns(4)
        sensor_cols[0].metric("Temperature", _number(latest_sensor.get("temperatureC"), " °C"))
        sensor_cols[1].metric("Humidity", _number(latest_sensor.get("humidityPercent"), "%"))
        sensor_cols[2].metric("Light sensor", {0: "Inactive", 1: "Active", None: "N/A"}.get(latest_sensor.get("lightStatus"), "N/A"))
        sound = latest_sensor.get("soundDetected")
        sensor_cols[3].metric("Sound", "Detected" if sound is True else "Not detected" if sound is False else "N/A")
        st.caption(f"Sequence {latest_sensor.get('sequence', 'N/A')} · source ESP32_{latest_sensor.get('sourceNodeId', 'N/A')} · received {latest_sensor.get('receivedAt', 'N/A')} · { 'fresh' if sensor_fresh else 'stale/historical' }")
    else:
        st.info("Temperature, humidity, light and sound: N/A")

    st.markdown("### C. ML routing decisions")
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
        st.markdown("**Python route-model shadow inference**")
        st.write({key: shadow.get(key) for key in
                  ("decision", "reason", "prediction", "nextHopId", "confidence", "improvement", "modelVersion")})
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
                st.session_state.p12_decision_log_error = f"Decision persistence failed: {exc}"
        if st.session_state.get("p12_decision_log_error"):
            st.warning(st.session_state.p12_decision_log_error)
        device_synced = bool(control_state and control_state.get("deviceEpoch") == control_state.get("epoch")
                             and control_state.get("deviceEnabled") is control_state.get("enabled"))
        if (control_state and device_synced and control_state.get("enabled") is True and configured_policy
                and shadow.get("decision") == "ELIGIBLE" and control_token):
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
                    st.session_state.p12_command_error = f"ML command submission failed: {exc}"
            else:
                st.session_state.p12_command_error = "ML command withheld: telemetry evidence is too close to expiry."
        if st.session_state.get("p12_last_ml_command"):
            st.caption(f"Latest ML command: {st.session_state.p12_last_ml_command.get('commandId')} · {st.session_state.p12_last_ml_command.get('status')}")
        if st.session_state.get("p12_command_error"):
            st.warning(st.session_state.p12_command_error)
        decision_cols = st.columns(5)
        decision_cols[0].metric("Prediction", str(latest_event.get("predictedClass", "N/A")))
        decision_cols[1].metric("Selected next hop", f"ESP32_{latest_event.get('selectedNextHopId')}" if latest_event.get("selectedNextHopId") is not None else "N/A")
        decision_cols[2].metric("Mode", latest_event.get("routingMode", "N/A") if routing_fresh else "STALE / N/A")
        decision_cols[3].metric("Forwarding result", latest_event.get("forwardingResult", "N/A"))
        decision_cols[4].metric("ML inputs", "Valid" if latest_event.get("featureValid") is True else "UNAVAILABLE")
        st.caption(f"ACK result: {latest_event.get('ackResult', 'N/A')} · sequence {latest_event.get('sequence', 'N/A')} · source uptime {latest_event.get('sourceUptimeMs', 'N/A')} ms · hop count {latest_event.get('hopCount', 'N/A')}")
        path_cols = st.columns(2)
        for col, title, key in ((path_cols[0], "Upper path · ESP32_02", "candidateUpper"), (path_cols[1], "Lower path · ESP32_03", "candidateLower")):
            path = latest_event.get(key) if isinstance(latest_event.get(key), dict) else {}
            col.markdown(f"**{title}**")
            col.write(f"Available: {path.get('available', 'N/A')} · PDR: {_number(path.get('pdr'), '%')} · latency: {_number(path.get('latencyMs'), ' ms')} · hops: {_number(path.get('hops'))}")
        feature_names = ["upper_available", "upper_pdr_estimate", "upper_latency_ms", "upper_hops", "lower_available", "lower_pdr_estimate", "lower_latency_ms", "lower_hops"]
        feature_values = latest_event.get("modelFeatures")
        st.dataframe(pd.DataFrame({"Model feature (Step 2 order)": feature_names, "Measured value": feature_values if isinstance(feature_values, list) and len(feature_values) == 8 else ["N/A"] * 8}), width="stretch", hide_index=True)
        if routing_fresh and latest_event.get("routingMode") == "ML_ACTIVE" and latest_event.get("forwardingResult") == "GATEWAY_RECEIVED":
            st.success("ML_ACTIVE · prediction controlled the selected route and the Gateway received this packet.")
        elif routing_fresh and latest_event.get("routingMode") == "BASELINE_FALLBACK":
            st.info("BASELINE_FALLBACK · model inputs were unavailable or model output did not control forwarding.")
        elif not routing_fresh:
            st.caption(f"Historical mode: {latest_event.get('routingMode', 'N/A')} · forwarding result {latest_event.get('forwardingResult', 'N/A')}")
    else:
        st.info("No routing events available. Prediction, candidate metrics and forwarding outcomes are N/A.")

    st.markdown("### D. Network performance")
    if interval_stats:
        perf = pd.DataFrame(interval_stats)
        perf["timestamp"] = pd.to_datetime(perf["timestamp"], utc=True, errors="coerce")
        perf = perf.dropna(subset=["timestamp"])
        left, right = st.columns(2)
        pdr_fig = go.Figure(go.Scatter(x=perf["timestamp"], y=perf["pdr"] * 100, mode="lines+markers", name="PDR %"))
        pdr_fig.update_layout(title="Measured delivery ratio by sent-counter interval", yaxis_title="PDR (%)", height=300, margin=dict(l=10,r=10,t=40,b=10))
        left.plotly_chart(pdr_fig, width="stretch")
        loss_fig = go.Figure(go.Scatter(x=perf["timestamp"], y=perf["loss"] * 100, mode="lines+markers", name="Packet loss %", line=dict(color="#ef4444")))
        loss_fig.update_layout(title="Measured packet loss by sent-counter interval", yaxis_title="Loss (%)", height=300, margin=dict(l=10,r=10,t=40,b=10))
        right.plotly_chart(loss_fig, width="stretch")
    else:
        st.info("PDR/loss graph: N/A until an interval between confirmed routing events is available.")
    performance_cols = st.columns(4)
    performance_cols[0].metric("End-to-end latency", "N/A · not measured in API contract")
    performance_cols[1].metric("Route changes", str(sum(row.get("routeChanged") is True for row in events)) if events else "N/A")
    performance_cols[2].metric("Gateway-confirmed transmissions", str(sum(row.get("forwardingResult") == "GATEWAY_RECEIVED" for row in events)) if events else "N/A")
    performance_cols[3].metric("Failed transmissions", "N/A · failed packets cannot reach this Gateway event API")

    st.markdown("### E. Routing event history")
    if events:
        history = []
        for row in sorted(events, key=lambda item: parse_timestamp(item.get("receivedAt")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
            selected = row.get("selectedNextHopId")
            history.append({
                "Timestamp": row.get("observedAt") or row.get("receivedAt") or "N/A",
                "Sequence": row.get("sequence", "N/A"),
                "Source": f"ESP32_{row.get('sourceNodeId')}" if row.get("sourceNodeId") is not None else "N/A",
                "Selected route": f"ESP32_01 → ESP32_{selected} → ESP32_04" if selected is not None else "N/A",
                "Prediction": row.get("predictedClass", "N/A"),
                "Mode": row.get("routingMode", "N/A"),
                "Forwarding": row.get("forwardingResult", "N/A"),
                "Route-change reason": row.get("routeChangeReason", "N/A"),
                "Source uptime ms": row.get("sourceUptimeMs", "N/A"),
            })
        st.dataframe(pd.DataFrame(history), width="stretch", hide_index=True)
    else:
        st.info("No routing history loaded. Refresh to query the P12-only event endpoint.")

    st.markdown("### Historical sensor records")
    if hardware_rows:
        st.dataframe(pd.DataFrame(hardware_rows), width="stretch", hide_index=True)
    else:
        st.caption("No historical hardware records are currently loaded.")
    st.caption("Simulation outputs remain under the Overview, Topology, Packet events, Performance and Model evaluation tabs; this tab only reads P12 API records.")

with live_p12_tab:
    _render_live_p12()
