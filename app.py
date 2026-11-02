import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from experiments.runner import SCENARIOS, run_suite
from ml.pipeline import train_model
from simulator.core import SimulationConfig, build_topology, run_simulation

st.set_page_config(page_title="Intelligent IoT Mesh Routing", page_icon="📡", layout="wide")
st.title("Machine Learning-Based Intelligent Routing Optimization")
st.caption("Low-Power IoT Mesh Network • reproducible synthetic simulation • not ESP32 measurements")

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

overview, topology_tab, events_tab, compare_tab, model_tab = st.tabs(["Overview", "Topology", "Packet events", "Performance", "Model evaluation"])
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
