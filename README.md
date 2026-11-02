# Machine Learning-Based Intelligent Routing Optimization for Low-Power IoT Mesh Networks

## Overview

This project studies routing choices for a low-power IoT mesh using two distinct software artifacts: a reproducible Python graph simulator with a synthetic-data Decision Tree policy, and an OMNeT++/INET packet-level AODV baseline. The ML policy is not integrated into INET. No physical ESP32 routing firmware or measured radio results are present.

## Problem and objectives

Low-power mesh links vary in quality; shortest-hop routing can select unreliable links. Project objective: explore whether a learned one-hop ACK-success estimate can help choose among loop-free next hops, measure behavior under controlled scenarios, and define a later four-node hardware prototype. Current evidence supports software experiments only.

## Architecture

- **Python simulation:** seeded graph, sequential packet forwarding, modeled per-link loss/latency, baseline minimum-hop and ML candidate scoring. See [architecture](docs/architecture/system_architecture.md).
- **ML:** Decision Tree estimates single-link ACK success from synthetic RSSI, latency, loss, throughput, and remaining-hop features. See [ML architecture](docs/architecture/ml_architecture.md).
- **Packet simulation:** six fixed INET `AodvRouter` nodes with UDP source/sink and scenario variants. This is AODV only. See [simulation architecture](docs/architecture/simulation_architecture.md).
- **Physical concept:** four ESP32 nodes, two relay corridors, sensors at source. Diagram: [final hardware architecture](diagrams/final_hardware_architecture.svg). It is a design proposal; assembly, firmware, and radio tests are unverified.

## Implemented features and evidence status

| Area | State | Evidence boundary |
|---|---|---|
| Python simulator and dashboard | Implemented locally | Seeded abstract graph model; not calibrated radio simulation |
| Python baseline and ML candidate selection | Implemented locally | Synthetic training labels; no INET integration |
| Generated training data and model | Included | Synthetic, reproducible; do not treat as measured observations |
| INET topology/configs | Source prepared | AODV baseline only; OMNeT++/INET build and runs unverified on authoring host |
| Custom INET ML forwarder | Not implemented | No ML-controlled packet forwarding claim |
| ESP32 prototype | Planned | No firmware or physical test results |

The checked-in Python aggregate CSV is a small illustrative snapshot from synthetic experiments. Re-run commands before analysis. Failure recall was **0.0** in the included model metadata; aggregate accuracy alone is not evidence of useful failure detection.

## Install

Python ML/dashboard setup is independent of OMNeT++: [ML setup](docs/installation/ML_SETUP.md). Packet simulation setup: [overview](docs/installation/INSTALLATION_OVERVIEW.md), [macOS](docs/installation/MACOS.md), [Windows](docs/installation/WINDOWS.md), [Linux](docs/installation/LINUX.md), and [simulation setup](docs/installation/SIMULATION_SETUP.md). Platform instructions document; only the current host's Python path can be exercised here.

## Quick start: Python experiments

```sh
python3.11 -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python tools/validation/validate_environment.py --python-only
python train_model.py
python run_experiments.py --trials 5 --packets 100 --seed 17 --nodes 6
streamlit run app.py
```

Generated data/model go to `ml/data/synthetic/` and `ml/models/`; fresh experiment CSVs go to `results/python/`. These generated paths are ignored by Git except checked-in summary evidence.

## Reproduction and results

- [Python simulation workflow](docs/simulation/simulation_workflow.md)
- [ML pipeline and evaluation](docs/machine_learning/model_training.md)
- [Checked-in result snapshot](results/README.md)
- [INET scenarios and commands](simulation/README.md)

## Repository map

```text
simulation/inet/  OMNeT++/INET topology, scenario INI/XML, SCA exporter, tests
simulator/        Python graph and packet simulator
routing/          Python baseline and ML next-hop policy
ml/               training/evaluation pipeline, synthetic dataset, model artifacts
experiments/      paired Python scenario runner
metrics/          Python metric calculations
results/          retained result snapshots and generated output location
hardware/         prototype notes and diagrams
reports/          project reports and review records
```

## Troubleshooting and limits

See [simulation troubleshooting](docs/simulation/troubleshooting.md), [environment setup](docs/installation/INSTALLATION_OVERVIEW.md), and [known limitations](docs/machine_learning/evaluation.md). Packet-level OMNeT++ results must not be conflated with Python graph-simulation outputs. No energy, calibrated radio, or physical hardware results are measured. Battery/BMS/charger selections require competent electrical review before construction; see [hardware status](docs/hardware/hardware_validation_status.md).
