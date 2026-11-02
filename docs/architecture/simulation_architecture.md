# Simulation architecture

`simulator/core.py` builds a six-node graph with two source-gateway corridors and executes packets sequentially. Loss uses deterministic per-packet/link draws for paired algorithm comparisons. Latency and congestion are simplified parameters. `simulation/inet/` defines six `AodvRouter` submodules over `UnitDiskRadioMedium`, UDPBasicApp traffic, UdpSink, a fixed topology and nine configurations. No project C++ exists. See [topology](../simulation/topology.md), [configurations](../simulation/configuration_guide.md), and [metric definitions](../simulation/metrics.md).
