# Configuration guide

INET INI file: `simulation/inet/simulations/mesh/omnetpp.ini`. Configs: `Normal` (AODV baseline), `DegradedPath` (range reduced to 190 m), `IncreasedInterference` (competing UDP traffic + modeled interference), `IncreasedPacketLoss` (higher competing offered load; not independent calibrated BER), `HighLatency` (100 kbps link rate), `Congestion` (competing relay flow), `RelayFailure`, `PreferredPathFailure`, `LinkRecovery` (XML lifecycle events). Equal-hop AODV paths do not guarantee a fixed first path. Failure/recovery labels describe configured events, not validated outcomes.

Python scenarios: `normal`, `degraded`, `preferred_link_failure`, `high_loss`, `high_latency`, `congestion`, `recovery`; both router modes run paired seeds. Python recovery restores preferred link after half the packet count; it is an abstract model distinct from INET lifecycle events.
