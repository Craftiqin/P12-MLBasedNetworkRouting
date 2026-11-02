# Simulation troubleshooting

- `inet`/`opp_run` not found: enter installed `opp_env shell inet-4.7.0`; these tools are not globally available from that environment.
- NED type not found: run from `simulation/inet`; pass `-n "src:$INET_ROOT/src"` and verify `INET_ROOT`.
- INET shared library missing: install/build INET through `opp_env`; do not add an unbuilt local path.
- output path error: create `simulation/inet/results` first; inspect write permission.
- Qtenv fails: confirm Qt/GUI support and graphical session; use Cmdenv on headless systems.
- no route after failure: inspect `.rt` and packet vectors; AODV convergence is event/seed dependent.
- do not use custom-router diagnostics as validated results. No custom INET router exists in this repository.
