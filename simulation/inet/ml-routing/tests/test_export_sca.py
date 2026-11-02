import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.export_sca import summarize


class ScaExportTests(unittest.TestCase):
    def test_derives_delivery_metrics_from_scalar_and_statistic_records(self):
        content = '''version 2
run test
attr configname "Normal"
scalar node[5].app[0] packetSent:count 10
scalar node[0].app[0] packetReceived:count 8
scalar node[0].app[0] packetReceived:sum(packetBytes) 1024
statistic node[0].app[0] endToEndDelay
field mean 0.25
field count 8
end
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.sca"
            path.write_text(content)
            result = summarize(path, payload_bytes=128, observation_seconds=4)

        self.assertEqual(result["config"], "Normal")
        self.assertEqual(result["packets_sent"], 10)
        self.assertEqual(result["packets_received"], 8)
        self.assertAlmostEqual(result["pdr"], 0.8)
        self.assertAlmostEqual(result["packet_loss_ratio"], 0.2)
        self.assertAlmostEqual(result["mean_end_to_end_delay_s"], 0.25)
        self.assertAlmostEqual(result["throughput_bps"], 2048)

    def test_cli_writes_csv_from_sca_fixture(self):
        content = '''version 2
run test
attr configname "Normal"
scalar node[5].app[0] packetSent:count 4
scalar node[0].app[0] packetReceived:count 3
scalar node[0].app[0] packetReceived:sum(packetBytes) 384
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = root / "results"
            results.mkdir()
            (results / "run.sca").write_text(content)
            output = root / "summary.csv"
            script = Path(__file__).parents[1] / "tools" / "export_sca.py"
            subprocess.run([sys.executable, str(script), str(results), "--output", str(output)],
                           check=True, capture_output=True, text=True)
            with output.open(newline="") as csv_file:
                row = next(csv.DictReader(csv_file))

        self.assertEqual(row["config"], "Normal")
        self.assertEqual(row["packets_sent"], "4.0")
        self.assertEqual(row["packets_received"], "3.0")
        self.assertEqual(row["pdr"], "0.75")


if __name__ == "__main__":
    unittest.main()
