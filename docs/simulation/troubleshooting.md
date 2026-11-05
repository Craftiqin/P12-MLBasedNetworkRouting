# Simulation troubleshooting

- `inet`/`opp_run` not found: source OMNeT++ and INET `setenv` scripts; check `OMNETPP_ROOT`, `INET_ROOT`, and `PATH`. See [native install setup](../installation/SIMULATION_SETUP.md).
- NED type not found: run from `simulation/inet`; pass `-n "src:$INET_ROOT/src"` and verify `INET_ROOT`.
- INET shared library missing: build INET using its official procedure, then rerun the ML package's `tools/configure_build.py`.
- output path error: create `simulation/inet/results` first; inspect write permission.
- Qtenv fails: confirm Qt/GUI support and graphical session; use Cmdenv on headless systems.
- Runner timeouts, finite-run limits, and current Qtenv evidence: see [run completion and Qtenv status](termination.md).
- no route after failure: inspect `.rt` and packet vectors; AODV convergence is event/seed dependent.
- ML packet-level forwarding is implemented in `simulation/inet/ml-routing`; do not infer that other scenarios or platforms passed from its local validation.
