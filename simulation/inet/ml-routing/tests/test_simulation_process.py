import sys
import unittest
from pathlib import Path

from tools.simulation_process import run_finite_simulation


ROOT = Path(__file__).resolve().parents[1]


class SimulationProcessTests(unittest.TestCase):
    def test_captures_clean_exit_and_elapsed_time(self):
        result = run_finite_simulation(
            [sys.executable, "-c", "print('out'); import sys; print('err', file=sys.stderr)"],
            ROOT, timeout_seconds=5,
        )
        self.assertFalse(result.timed_out)
        self.assertEqual(result.returncode, 0)
        self.assertIn("out", result.stdout)
        self.assertIn("err", result.stderr)
        self.assertGreaterEqual(result.elapsed_seconds, 0)
        self.assertTrue(result.started_at_utc)
        self.assertTrue(result.ended_at_utc)

    def test_timeout_terminates_child_and_keeps_partial_output(self):
        result = run_finite_simulation(
            [sys.executable, "-u", "-c", "import time; print('started', flush=True); time.sleep(30)"],
            ROOT, timeout_seconds=0.2, terminate_grace_seconds=1,
        )
        self.assertTrue(result.timed_out)
        self.assertIsNotNone(result.returncode)
        self.assertIn("started", result.stdout)
        self.assertLess(result.elapsed_seconds, 5)


if __name__ == "__main__":
    unittest.main()
