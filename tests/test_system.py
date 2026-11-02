import pandas as pd
import pytest

from experiments.runner import SCENARIOS, run_suite
from ml.pipeline import generate_dataset, load_model, train_model
from metrics.core import summarize
from routing.engines import ml_next_hop
from simulator.core import Packet, SimulationConfig, build_topology, run_simulation, suppress_duplicate


def test_topology_has_alternative_routes_and_six_nodes():
    graph=build_topology()
    assert graph.number_of_nodes() >= 6
    assert len(list(__import__('networkx').all_simple_paths(graph,"S","G"))) >= 2


def test_baseline_delivers_and_packet_has_required_fields():
    packet=Packet(1,"S","G",0.0)
    assert packet.history == []
    result=run_simulation(build_topology(loss_probability=0),SimulationConfig(packet_count=4,seed=5),"baseline")
    assert result["metrics"]["pdr"] == 1
    assert result["packets"].iloc[0].route.startswith("S->")


def test_link_failure_and_disconnected_gateway_handled():
    graph=build_topology(loss_probability=0)
    graph["S"]["R1"]["available"] = False
    graph["S"]["R3"]["available"] = False
    result=run_simulation(graph,SimulationConfig(packet_count=2),"baseline")
    assert result["metrics"]["pdr"] == 0
    assert set(result["packets"].status) == {"route_unavailable"}


def test_loss_hop_limit_and_loop_safeguards():
    graph=build_topology(loss_probability=1)
    lost=run_simulation(graph,SimulationConfig(packet_count=2),"baseline")
    assert set(lost["packets"].status) == {"packet_loss"}
    loop=run_simulation(build_topology(loss_probability=0),SimulationConfig(packet_count=2,hop_limit=1),"baseline")
    assert set(loop["packets"].status) == {"hop_limit"}


def test_seed_reproducibility_and_ml_changes_decisions(tmp_path):
    graph=build_topology()
    baseline=run_simulation(graph,SimulationConfig(packet_count=30,seed=42),"baseline")
    repeat=run_simulation(graph,SimulationConfig(packet_count=30,seed=42),"baseline")
    pd.testing.assert_frame_equal(baseline["packets"],repeat["packets"])
    model,metrics,data=train_model(runs=24,seed=42,data_path=tmp_path/"mesh-test.csv",model_path=tmp_path/"mesh-test.joblib")
    assert data.synthetic.all() and metrics["test_runs"]
    ml=run_simulation(graph,SimulationConfig(packet_count=30,seed=42,scenario="degraded"),"ml",model)
    assert len(ml["packets"]) == 30


def test_dataset_repeatable_and_has_multiple_classes():
    a=generate_dataset(runs=8,seed=9)
    b=generate_dataset(runs=8,seed=9)
    pd.testing.assert_frame_equal(a,b)
    assert a.delivery_success.nunique()==2


def test_duplicate_suppression_and_ml_hysteresis():
    seen=set()
    assert not suppress_duplicate(seen,"R1",9)
    assert suppress_duplicate(seen,"R1",9)
    graph=build_topology(loss_probability=0)
    class CertainModel:
        classes_=[0,1]
        def predict_proba(self, rows): return [[.1,.9] for _ in rows]
    next_hop,reason=ml_next_hop(graph,"S","G",["S"],CertainModel(),0,"R3")
    assert next_hop=="R3" and reason=="ml_hysteresis"


def test_model_load_failure_and_experiment_csv_exports(tmp_path):
    with pytest.raises(FileNotFoundError): load_model(tmp_path/"missing.joblib")
    invalid=tmp_path/"bad.joblib"; invalid.write_text("not a model")
    with pytest.raises(Exception): load_model(invalid)
    raw,aggregate=run_suite(trials=1,packets=3,seed=3,output_dir=tmp_path,model=None)
    assert len(raw)==14 and len(aggregate)==14
    assert (tmp_path/"trial_results.csv").exists() and (tmp_path/"aggregate_results.csv").exists()


def test_metrics_and_csv_scenarios():
    packets=pd.DataFrame([{"delivered":True,"latency_s":.1},{"delivered":False,"latency_s":float('nan')}])
    m=summarize(packets,64,2)
    assert m["pdr"] == .5 and m["packet_loss_rate"] == .5
    assert m["throughput_kbps"] == .256
    assert SCENARIOS == ["normal","degraded","preferred_link_failure","high_loss","high_latency","congestion","recovery"]
