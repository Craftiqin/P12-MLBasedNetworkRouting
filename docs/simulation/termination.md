# OMNeT++ run completion and Qtenv status

## Batch runs

Use Cmdenv for reproducible, finite experiments. ML and AODV runners default to
Cmdenv and use a 60-second wall-clock limit. On timeout, they send SIGTERM to
the simulator process group, wait five seconds, and use SIGKILL only if it is
still alive. The manifest and stdout/stderr logs identify timeout or simulator
failure; incomplete runs are not marked validated.

The normal ML/AODV configurations have a 60-second simulation-time limit and
stop source traffic at 58 seconds. `MLVisualDemo` has a 16-second limit and
stops traffic at 14 seconds. The runner validates generated results and ML
traces before reporting success. Each run receives a fresh directory under
`simulation/inet/ml-routing/experiments/runs/`.

From `simulation/inet/ml-routing`, with OMNeT++ and INET environments active:

```sh
.ml-venv/bin/python tools/run_ml_experiment.py --config MLVisualDemo --seed-set 17
.ml-venv/bin/python tools/run_ml_experiment.py --config MLRoutePreference --seed-set 17
.ml-venv/bin/python tools/run_aodv_experiment.py --ui Cmdenv --config Normal --seed-set 17
```

## Interactive Qtenv

Qtenv is interactive. The ML runner launches it detached and returns a PID and
log path with `interactive_started`; this means startup was requested, not
that the simulation finished or the visuals passed review. Run
`MLVisualDemo` with `--ui Qtenv`, then press **Run/F5** in the visible window.
The window can remain open after the finite simulation ends.

## Local Qtenv validation record

The source workspace run `20261103T084440Z-ML-MLVisualDemo` remained marked
`interactive_started`. Its log shows NED and image loading; its partial event
log and missing scalar file do not establish a completed simulation. These
artifacts were not copied into this repository as validated results.

An official-P12 launch on 2026-11-05 (`20261105T163208Z-ML-MLVisualDemo`)
reached NED and image loading. The desktop inspection surface did not expose a
Qtenv window. The simulator process was using 98.6% CPU after 39 seconds; it
was stopped with SIGTERM because it could not be inspected or controlled. No
scalar result was produced. Qtenv window rendering, packet animation, labels,
and route overlays therefore remain **unverified**. Use the completed Cmdenv
results for current simulation evidence; do not treat Qtenv launch as visual
validation.
