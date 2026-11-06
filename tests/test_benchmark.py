"""Guard search coverage so catalog edits can't quietly lose phrases or misroute them."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import benchmark

COVERAGE_FLOOR = 0.95


class BenchmarkTests(unittest.TestCase):
    def test_coverage_stays_above_the_floor(self):
        collections, _ = benchmark.measure()
        for name, result in collections.items():
            hits = result["total"] - len(result["missed"])
            self.assertGreaterEqual(hits / result["total"], COVERAGE_FLOOR, (name, result["missed"]))

    def test_known_phrases_reach_the_right_card_first(self):
        self.assertEqual(benchmark.measure()[1], {})


if __name__ == "__main__":
    unittest.main()
