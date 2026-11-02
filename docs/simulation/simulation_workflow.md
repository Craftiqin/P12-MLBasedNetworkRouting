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

Install compatible OMNeT++/INET first; commands are in [`simulation/README.md`](../../simulation/README.md). Configs are AODV, not ML. `Normal` is baseline. Keep raw `.sca`, `.vec`, `.rt` artifacts for evidence; exporter CSV is derived. INET is unavailable on current host, therefore compile, packet forwarding, Qtenv and scenario results are unverified.

## Regression checks

Python: `python -m pytest -q`. SCA exporter parser: from `simulation/inet`, `python -m unittest discover -s tests -v`. No claim of tests on unexecuted platforms.
