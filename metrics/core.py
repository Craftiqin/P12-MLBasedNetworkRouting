from __future__ import annotations

import pandas as pd


def summarize(packet_results: pd.DataFrame, payload_bytes: int, duration_s: float) -> dict:
    """Metrics: latency over delivered packets only; PDR denominator is generated packets."""
    if packet_results.empty:
        return {"pdr":0.0,"packet_loss_rate":1.0,"mean_latency_ms":float("nan"),
                "throughput_kbps":0.0,"packets_generated":0,"packets_delivered":0}
    delivered = packet_results[packet_results["delivered"]]
    pdr = float(len(delivered) / len(packet_results))
    return {"pdr":pdr,"packet_loss_rate":1-pdr,
            "mean_latency_ms":float(delivered.latency_s.mean()*1000) if len(delivered) else float("nan"),
            "median_latency_ms":float(delivered.latency_s.median()*1000) if len(delivered) else float("nan"),
            "p95_latency_ms":float(delivered.latency_s.quantile(.95)*1000) if len(delivered) else float("nan"),
            "throughput_kbps":float(len(delivered)*payload_bytes*8/max(duration_s, 1e-12)/1000),
            "packets_generated":len(packet_results),"packets_delivered":len(delivered)}
