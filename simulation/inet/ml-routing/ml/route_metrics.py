"""Metric calculation for explicit per-packet trace rows; no routing inference."""

from statistics import mean


def summarize(packet_rows, observation_seconds, failure_time_s=None, route_recovery_s=None):
    sent_rows = [row for row in packet_rows if row.get("generated", True)]
    delivered = [row for row in sent_rows if row.get("received", False)]
    sent = len(sent_rows)
    received = len(delivered)
    payload_bits = sum(int(row.get("payload_bytes", 0)) * 8 for row in delivered)
    delays = [float(row["received_s"]) - float(row["created_s"]) for row in delivered]
    hops = [int(row["hops"]) for row in delivered]
    control = sum(int(row.get("control_packets", 0)) for row in sent_rows)
    duplicates = sum(int(row.get("duplicate_drops", 0)) for row in sent_rows)
    hop_limit_drops = sum(int(row.get("hop_limit_drops", 0)) for row in sent_rows)
    return {
        "packets_sent": sent,
        "packets_received": received,
        "pdr": received / sent if sent else None,
        "packet_loss": sent - received,
        "mean_end_to_end_delay_s": mean(delays) if delays else None,
        "throughput_bps": payload_bits / observation_seconds if observation_seconds > 0 else None,
        "mean_packet_hops": mean(hops) if hops else None,
        "routing_control_packets": control,
        "routing_overhead_ratio": control / sent if sent else None,
        "duplicate_drops": duplicates,
        "hop_limit_drops": hop_limit_drops,
        "route_recovery_s": route_recovery_s,
        "failure_time_s": failure_time_s,
    }
