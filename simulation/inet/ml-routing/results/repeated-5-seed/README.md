# Paired trial summary

Five matched seed sets (17–21), each run sequentially under AODV and ML. CSV omits local absolute run paths so it is portable. Aggregates contain mean and sample standard deviation.

| Condition | Metric | AODV | Decision Tree |
|---|---|---:|---:|
| Healthy | PDR | 0.9993 ± 0.0016 | 0.9600 ± 0.0894 |
|  | Delay (ms) | 5.21 ± 2.99 | 89.37 ± 194.82 |
|  | Throughput (bit/s) | 5116.3 ± 8.2 | 4915.2 ± 457.9 |
| Degraded reliability¹ | PDR | 0.2900 ± 0.1615 | 0.6929 ± 0.0621 |
|  | Delay (ms) | 4293.5 ± 2657.3 | 4798.2 ± 547.8 |
|  | Throughput (bit/s) | 1484.8 ± 827.1 | 3547.4 ± 318.0 |
| Increased latency² | PDR | 0.9986 ± 0.0032 | 0.9671 ± 0.0442 |
|  | Delay (ms) | 22.82 ± 7.43 | 283.21 ± 410.08 |
|  | Throughput (bit/s) | 5112.7 ± 16.4 | 4951.8 ± 226.3 |
| Relay failure | PDR | 0.9986 ± 0.0020 | 0.9800 ± 0.0447 |
|  | Delay (ms) | 5.55 ± 2.90 | 240.91 ± 251.05 |
|  | Throughput (bit/s) | 5112.7 ± 10.0 | 5017.6 ± 229.0 |
| Relay failure + restart | Recovery interval (s)³ | 0.109 ± 0.240 | 2.954 ± 4.031 |

Decision Tree packet hop count was 3 ± 0 in delivered trials. AODV packet-level hop count is not instrumented. Routing-control overhead is not measured; active-probe bytes are excluded from current counters. Latency and delivery estimates supplied to the tree are configured model inputs, not runtime observations. Actual link/node state comes from simulation events; relay restart eligibility requires an end-to-end probe reply.

¹ Heavy competing UDP flow with shared-medium interference. ² Lower PHY bitrate. ³ Interval to the first gateway delivery after failure; this is a service metric, not proof that the restarted A2 relay became eligible. In all ML restart trials, the probe received no reply; A2 stayed ineligible and alternate route carried traffic. Failure was configured at 30 s and restart at 45 s. ML failure detection and route change occurred at 30 s in observed scenario traces; recovery probe attempts began after restart. The first successful delivery interval can vary by seed and is reported as mean ± sample SD.

These five-seed, single-host simulation results are scenario-specific and variable. They do not establish general ML superiority. Full simulator traces remain in the local workspace and are not included here.
