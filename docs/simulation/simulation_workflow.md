# Python and INET simulation workflow

## Python graph simulator

From repository root with ML dependencies installed:

```sh
python tools/validation/validate_environment.py --python-only
python train_model.py
python run_experiments.py --trials 5 --packets 100 --seed 17 --nodes 6
python -m pytest -q
```

These create synthetic dataset/model and paired outputs. For quick check use `--trials 1 --packets 5`; this is smoke execution, not reported evaluation. The seven scenarios and paired baseline/ML seeds are in `experiments/runner.py`. Dashboard: `streamlit run app.py`.

## INET packet-level AODV

The preserved AODV workflow is in [simulation README](../../simulation/README.md); ML packet forwarding is in [ML routing README](../../simulation/inet/ml-routing/README.md). The ML project was locally built/run on macOS with OMNeT++ 6.5.0 + INET 4.7.0. Its four live integration tests skip in shells where inet/INET_ROOT are absent. Qtenv visual inspection and Windows/Linux builds remain unverified. Curated five-seed results and limitations are checked in; raw run directories are local.

## Regression checks

Python: `python -m pytest -q`. SCA exporter parser: from `simulation/inet`, `python -m unittest discover -s tests -v`. No claim of tests on unexecuted platforms.
