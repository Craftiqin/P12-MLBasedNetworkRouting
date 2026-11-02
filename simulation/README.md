# INET packet-level simulation

This folder contains an OMNeT++/INET six-router AODV wireless baseline. OMNeT++ supplies discrete-event simulation and Qtenv visualization; INET supplies networking, wireless medium, IPv4, AODV, UDP apps and statistics. Current code is NED/INI/XML + Python SCA exporter; there is no custom C++ router and no ML integration.

## Install and build

Follow [`docs/installation/SIMULATION_SETUP.md`](../docs/installation/SIMULATION_SETUP.md) and the matching platform guide. Preferred upstream install pattern uses compatible versions via `opp_env`. Project has no custom C++ or Makefile; INET itself must be compiled by `opp_env` or upstream manual procedure.

## Run

Enter the project config directory from repo root, inside compatible `opp_env` shell:

```sh
cd simulation/inet
mkdir -p results
inet -u Cmdenv -n "src:$INET_ROOT/src" -f simulations/mesh/omnetpp.ini -c Normal -r 0
python3 tools/export_sca.py results --output results/omnet_summary.csv
```

Qtenv:

```sh
inet -u Qtenv -n "src:$INET_ROOT/src" -f simulations/mesh/omnetpp.ini -c Normal
```

Graphical launch documented, not visually tested here. `tools/scripts/run_simulation.sh [Config] [RunNumber]` is a convenience wrapper when invoked from any project directory in a POSIX shell.

Configs (all AODV): `Normal`, `DegradedPath`, `IncreasedInterference`, `IncreasedPacketLoss`, `HighLatency`, `Congestion`, `RelayFailure`, `PreferredPathFailure`, `LinkRecovery`. Inspect semantics in [configuration guide](../docs/simulation/configuration_guide.md). Example sweep from `simulation/inet`:

```sh
for config in Normal DegradedPath IncreasedInterference IncreasedPacketLoss HighLatency Congestion RelayFailure PreferredPathFailure LinkRecovery; do
  inet -u Cmdenv -n "src:$INET_ROOT/src" -f simulations/mesh/omnetpp.ini -c "$config" -r 0 || exit 1
done
```

Windows users: recommended path runs commands in WSL2 Linux shell. For native MinGW, use OMNeT++ shell and verify `inet` lookup; NED path separators and shell syntax differ. No native Windows execution was tested.

## Inspect evidence and regression

Raw `.sca` scalars, `.vec` vectors, `.rt` route-table logs land in `simulation/inet/results/`, configured relative to this current directory. `export_sca.py` derives available PDR, loss, received payload throughput and mean delay. Validate against raw counts; exporter does not calculate hop count, route switches, recovery time or overhead. Tests from this directory: `python -m unittest discover -s tests -v`.

AODV discovers/repairs routes reactively; equal-hop corridors do not force a particular route. Configs are not validated experiments: OMNeT++/INET were unavailable during authoring. Preserve traces when runs are performed. See [packet topology](../docs/simulation/topology.md), [metrics](../docs/simulation/metrics.md), [troubleshooting](../docs/simulation/troubleshooting.md).
