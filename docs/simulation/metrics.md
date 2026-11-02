# Metric definitions and evidence

Python definitions are in `metrics/core.py` and `simulator/core.py`: PDR = delivered/generated; packet loss = 1-PDR; latency summaries include delivered packets only; throughput = delivered payload bits divided by offered-workload observation duration. Route switches count changes in a node's chosen next hop across packets. Recovery time is first delivered packet after modeled restoration; no recovery is missing/censored. Control overhead and energy are not modeled.

INET exporter `simulation/inet/tools/export_sca.py` extracts available sent/received counts and scalar stats, derives PDR/loss, receiver payload throughput, and mean delay only where suitable records exist. It does not calculate average hop count, route-switch count, recovery time, or control overhead. Raw `.sca`/`.vec`/`.rt` remain source evidence; verify CSV against source files.
