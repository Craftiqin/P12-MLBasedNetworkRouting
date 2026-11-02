import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.build_dashboard import build_packet_rows, generate, read_route_changes, read_vectors


class DashboardEvidenceTests(unittest.TestCase):
    def test_packet_ids_pdr_duplicates_and_hop_limitations(self):
        fixture = '''version 3
vector 10 IoTMeshNetwork.node[5].app[0] packetSent:vector(packetBytes) ETV
vector 11 IoTMeshNetwork.node[0].app[0] packetReceived:vector(packetBytes) ETV
vector 12 IoTMeshNetwork.node[0].app[0] rcvdPkSeqNo:vector ETV
vector 13 IoTMeshNetwork.node[0].app[0] endToEndDelay:vector ETV
10 1 2.0 128
10 2 2.2 128
10 3 2.4 128
11 4 2.01 128
11 5 2.21 128
12 4 2.01 0
12 5 2.21 0
13 4 2.01 0.01
13 5 2.21 0.01
'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "run.vec"
            path.write_text(fixture)
            packets, details = build_packet_rows(read_vectors(path))
        self.assertEqual([row["packet_id"] for row in packets], [0, 1, 2])
        self.assertEqual(details["unique_received_count"], 1)
        self.assertEqual(details["duplicate_received_ids"], [0])
        self.assertEqual([row["delivery_status"] for row in packets],
                         ["delivered", "not_received_by_end", "not_received_by_end"])
        self.assertTrue(all(row["hop_count"] is None for row in packets))

    def test_dashboard_csv_and_summary_agree_with_vectors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sca = root / "Normal-#0.sca"
            vec = root / "Normal-#0.vec"
            rt = root / "Normal-#0.rt"
            output = root / "dashboard"
            sca.write_text('''version 3
attr configname "Normal"
attr seedset 17
scalar IoTMeshNetwork.node[0].app[0] packetReceived:sum(packetBytes) 256
''')
            vec.write_text('''version 3
vector 10 IoTMeshNetwork.node[5].app[0] packetSent:vector(packetBytes) ETV
vector 11 IoTMeshNetwork.node[0].app[0] packetReceived:vector(packetBytes) ETV
vector 12 IoTMeshNetwork.node[0].app[0] rcvdPkSeqNo:vector ETV
vector 13 IoTMeshNetwork.node[0].app[0] endToEndDelay:vector ETV
10 1 2.0 128
10 2 2.2 128
11 3 2.01 128
11 4 2.21 128
12 3 2.01 0
12 4 2.21 1
13 3 2.01 0.01
13 4 2.21 0.01
''')
            rt.write_text("")
            summary = generate(sca, vec, rt, output, 2, 4, root / "omnetpp.ini")
            with (output / "packet_outcomes.csv").open(newline="") as stream:
                packets = list(csv.DictReader(stream))
            serialized = json.loads((output / "summary.json").read_text())
            self.assertEqual(len(packets), summary["generated_unique_application_packets"])
            self.assertEqual(serialized["received_unique_application_packets"], 2)
            self.assertAlmostEqual(serialized["packet_delivery_ratio"], 1.0)
            self.assertEqual(serialized["packet_level_hop_count"], "Not measured")
            self.assertEqual(serialized["routing_control_overhead"], "Not measured")
            self.assertTrue((output / "index.html").exists())
            self.assertIn("ML comparison pending", (output / "01-pdr.svg").read_text())
            self.assertIn("Not measured", (output / "04-hop-count.svg").read_text())

    def test_route_change_and_recovery_use_actual_trace_times(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sca, vec, rt = root / "RelayFailure.sca", root / "RelayFailure.vec", root / "RelayFailure.rt"
            sca.write_text('''version 3
attr configname "RelayFailure"
attr seedset 17
config sim-time-limit 60s
scalar IoTMeshNetwork.node[0].app[0] packetReceived:sum(packetBytes) 256
''')
            vec.write_text('''version 3
vector 10 IoTMeshNetwork.node[5].app[0] packetSent:vector(packetBytes) ETV
vector 11 IoTMeshNetwork.node[0].app[0] packetReceived:vector(packetBytes) ETV
vector 12 IoTMeshNetwork.node[0].app[0] rcvdPkSeqNo:vector ETV
vector 13 IoTMeshNetwork.node[0].app[0] endToEndDelay:vector ETV
10 1 2.0 128
10 2 30.4 128
11 3 2.01 128
11 4 30.6 128
12 3 2.01 0
12 4 30.6 1
13 3 2.01 0.01
13 4 30.6 0.2
''')
            rt.write_text('''+R #0 2s IoTMeshNetwork.node[5] 10.0.0.6 10.0.0.1/32 10.0.0.5 wlan0
*R #0 30.5s IoTMeshNetwork.node[5] 10.0.0.6 10.0.0.1/32 10.0.0.3 wlan0
''')
            scenarios = root / "scenarios"
            scenarios.mkdir()
            (scenarios / "relay_failure.xml").write_text('<scenario><crash t="30s" module="node[4]"/></scenario>')
            output = root / "dashboard"
            summary = generate(sca, vec, rt, output, 2, 58, root / "omnetpp.ini")
            self.assertEqual(summary["route_change_events"], 1)
            self.assertEqual(summary["failure_time_s"], 30.0)
            self.assertEqual(summary["first_post_failure_delivery_s"], 30.6)
            self.assertAlmostEqual(summary["route_recovery_time_s"], 0.6)
            events = read_route_changes(rt)
            self.assertEqual([event["changed"] for event in events], [False, True])


if __name__ == "__main__":
    unittest.main()
