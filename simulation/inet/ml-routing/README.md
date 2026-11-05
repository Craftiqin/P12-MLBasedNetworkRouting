# OMNeT++/INET Decision Tree routing

Self-contained packet-level ML routing project. AODV baseline remains in the parent `simulation/inet/` project. This folder adds a separate `MeshRoutingApp` configuration that runs generated Decision Tree inference at packet decision time and forwards packets over the selected route.

## Verified host and evidence boundary

Locally built and run on macOS 27, Apple Silicon M1, with OMNeT++ 6.5.0 and INET 4.7.0. INET's published compatibility table currently names OMNeT++ 6.4 with INET 4.7.0; this repository's 6.5.0 pairing passed local build and simulation checks, but Windows/Linux builds are **not tested**. See the cross-platform guides in [`docs/installation`](../../../docs/installation/INSTALLATION_OVERVIEW.md).

The 600-row training dataset is reproducible synthetic controlled-route data, not INET packet data or hardware measurements. Held-out accuracy: 96.67% over 120 rows. Runtime PDR/latency estimates are configured features; `NodeStatus` availability and active route probes are runtime evidence. This does not establish that ML is generally superior to AODV.

Fresh repeated-run summary lives in [`results/repeated-5-seed`](results/repeated-5-seed/). It covers five seeds for healthy, interference-stressed, increased-latency, relay-failure, and relay-recovery conditions. AODV packet-level hop count and control-byte overhead are not measured. Raw run directories remain in the local simulation workspace unless separately archived.

## Install and build

1. Install OMNeT++ and INET using the matching [platform guide](../../../docs/installation/INSTALLATION_OVERVIEW.md).
2. Activate both environments in the same shell. Exact macOS example:

```sh
source "$OMNETPP_ROOT/.venv/bin/activate"
source "$OMNETPP_ROOT/setenv" -q
source "$INET_ROOT/setenv"
cd path/to/P12-Ganesh/simulation/inet/ml-routing
python3 -m venv .ml-venv
.ml-venv/bin/python -m pip install -r ml/requirements.txt
.ml-venv/bin/python tools/configure_build.py
```

`configure_build.py` finds the compiled INET library under `$INET_ROOT/out`, generates a local Makefile, and builds serially. Windows users must run it from OMNeT++'s MinGW shell or WSL2. Linux/macOS builds also use one job by default for low-memory systems.

## Reproduce model and run

```sh
.ml-venv/bin/python ml/generate_route_dataset.py \
  --output ml/local-training/route_scenarios.csv --runs 100 --seed 20261101
.ml-venv/bin/python ml/train_tree.py \
  --data ml/local-training/route_scenarios.csv \
  --model ml/local-training/route_tree.json \
  --metrics ml/local-training/evaluation.json \
  --header ml/local-training/DecisionTreeModel.h
.ml-venv/bin/python tools/run_ml_experiment.py --config MLRoutePreference --seed-set 17
.ml-venv/bin/python tools/run_aodv_experiment.py --ui Cmdenv --config Normal --seed-set 17
.ml-venv/bin/python -m unittest discover -s tests -v
```

`MLRoutePreference` exercises preferred-route selection; `MLPreferredPathFailure`
checks failover; `MLVisualDemo` is a shorter 16-second animation profile. AODV
baseline uses `CleanVisualDemo` or `Normal`. The runners default to finite
Cmdenv, apply a 60-second wall-clock timeout, and preserve stdout/stderr and
status manifests. Use `--ui Qtenv` for an interactive run; runner returns PID
and log path while Qtenv stays open.

Each experiment creates a new UTC-stamped `experiments/runs/` directory. Local build and run outputs are ignored by Git; curated, path-sanitized five-seed results are in [`results/repeated-5-seed`](results/repeated-5-seed/). Paired repetition across five scenarios and seeds:

```sh
.ml-venv/bin/python tools/run_paired_trials.py \
  --seeds 17 18 19 20 21 \
  --conditions healthy degraded_reliability increased_latency relay_failure relay_recovery
```

The runner executes sequentially, validates matching seed sets and traffic manifests, and writes per-run folders plus means and sample standard deviations. It preserves old artifacts.

## Qtenv

From this folder with OMNeT++/INET environments active, launch the short ML
demo through the platform-aware runner:

```sh
.ml-venv/bin/python tools/run_ml_experiment.py --config MLVisualDemo --ui Qtenv --seed-set 17
```

For AODV view, use `tools/run_aodv_experiment.py --ui Qtenv --config CleanVisualDemo`.
Qtenv visual correctness is not established by process launch; inspect packet
animation, route overlay, and node layout in the live window.

## Routing and safety details

- Decision input order is fixed in `ml/route_policy.py`, generated header, and parity tests.
- The predicted route is validated against candidate availability; invalid/no-route predictions use safe fallback or drop.
- Relay forwarding follows packet route metadata with duplicate suppression, loop checks, and hop limit.
- Reused UDP packets clear INET's stale `SocketInd` before resubmission.
- A restarted relay is **not** considered ready from `NodeStatus::UP`. Runtime sends an end-to-end request/return probe and only restores route eligibility after proof. In the current restart scenario, the probe does not return, so the relay correctly remains ineligible. A2 restart recovery is therefore unresolved; service remains on the alternate route.
- INFO output and `events.csv` report actual packet generation, receive, forwarding, selection, delivery, explicit drops, failures, route changes, and probe events. Network-level loss reason is reported as unresolved when no gateway delivery is observed.
- Probe/control bytes are not included in routing-overhead metrics. AODV hop count is also not measured.
