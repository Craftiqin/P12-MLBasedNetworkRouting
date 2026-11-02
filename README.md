# Machine Learning-Based Intelligent Routing Optimization for Low-Power IoT Mesh Networks

## Overview

This project studies routing choices for a low-power IoT mesh using a reproducible Python graph simulator and an OMNeT++/INET packet-level simulation. The INET implementation now contains a separate Decision Tree forwarder alongside the preserved AODV baseline. No physical ESP32 routing firmware or measured radio results are present.

## Problem and objectives

Low-power mesh links vary in quality; shortest-hop routing can select unreliable links. Project objective: explore whether a learned one-hop ACK-success estimate can help choose among loop-free next hops, measure behavior under controlled scenarios, and define a later four-node hardware prototype. Current evidence supports software experiments only.

## Architecture

- **Python simulation:** seeded graph, sequential packet forwarding, modeled per-link loss/latency, baseline minimum-hop and ML candidate scoring. See [architecture](docs/architecture/system_architecture.md).
- **ML:** Decision Tree estimates single-link ACK success from synthetic RSSI, latency, loss, throughput, and remaining-hop features. See [ML architecture](docs/architecture/ml_architecture.md).
- **Packet simulation:** preserved six-router AODV baseline plus a custom Decision Tree forwarder whose predictions choose real next hops. See [AODV baseline](simulation/README.md) and [ML routing implementation](simulation/inet/ml-routing/README.md).
- **Physical concept:** four ESP32 nodes, two relay corridors, sensors at source. Diagram: [final hardware architecture](diagrams/final_hardware_architecture.svg). It is a design proposal; assembly, firmware, and radio tests are unverified.

## Implemented features and evidence status

| Area | State | Evidence boundary |
|---|---|---|
| Python simulator and dashboard | Implemented locally | Seeded abstract graph model; not calibrated radio simulation |
| Python baseline and ML candidate selection | Implemented locally | Synthetic training labels; Python model is separate from INET tree |
| Generated training data and model | Included | Synthetic, reproducible; do not treat as measured observations |
| INET AODV baseline | Preserved and rerun | Paired comparison and metrics limitations documented in ML routing results |
| Custom INET ML forwarder | Implemented and locally validated | macOS 27 / Apple Silicon M1 only; Qtenv visual inspection and relay restart recovery remain incomplete |
| ESP32 prototype | Planned | No firmware or physical test results |

The checked-in Python link-model snapshot reports failure recall **0.0**; a fresh run recorded **0.0377**. The separate INET route-selection tree is also synthetic. Its five-seed AODV comparison is scenario-specific; it does not establish general ML superiority. See [curated INET results](simulation/inet/ml-routing/results/repeated-5-seed/README.md) and [evidence limits](reports/final_submission/report_validation_summary.md).

## Install

Python ML/dashboard setup is independent of OMNeT++: [ML setup](docs/installation/ML_SETUP.md). Packet simulation setup: [overview](docs/installation/INSTALLATION_OVERVIEW.md), [macOS](docs/installation/MACOS.md), [Windows](docs/installation/WINDOWS.md), [Linux](docs/installation/LINUX.md), and [simulation setup](docs/installation/SIMULATION_SETUP.md). Native OMNeT++/INET build and experiment runs were validated on this macOS Apple Silicon host. Windows and Linux instructions are untested.

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
