"""Smoke test for the Direction A benchmark prototype (benchmarks/law_citation_bench).

Runs under the repo's CI (``python -S -m unittest discover -s tests -t .``).
It exercises dataset generation + a baseline run without any network or
third-party dependency, keeping the benchmark self-verifying.
"""
import csv
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(os.path.dirname(HERE), "benchmarks", "law_citation_bench")
sys.path.insert(0, BENCH)

from build_dataset import build, DEFAULT_N  # noqa: E402
from run import run  # noqa: E402


class BenchmarkSmokeTest(unittest.TestCase):
    def test_dataset_builds_500(self):
        rows, total = build(DEFAULT_N, 20260809)
        self.assertEqual(len(rows), DEFAULT_N)
        self.assertEqual(sum(1 for r in rows if r["task"] == "T1"), 200)
        self.assertEqual(sum(1 for r in rows if r["task"] == "T2"), 200)
        self.assertEqual(sum(1 for r in rows if r["task"] == "T3"), 100)
        self.assertTrue(all(
            r["qid"].startswith(("T1-", "T2-", "T3-")) for r in rows))

    def test_baseline_run_produces_leaderboard(self):
        rows, _ = build(50, 20260809)
        tmp_ds = tempfile.mktemp(suffix=".jsonl")
        with open(tmp_ds, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        out = tempfile.mktemp(suffix=".csv")
        out_dir = os.path.dirname(out)
        row = run(tmp_ds, "random", out, 0)
        self.assertIn("overall", row)
        self.assertTrue(os.path.isfile(out))
        with open(out, encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            self.assertIn("model", next(reader))
        # M3 report artifacts must also be produced (offline, no network)
        for art in ("leaderboard.json", "leaderboard.md", "leaderboard.html"):
            self.assertTrue(
                os.path.isfile(os.path.join(out_dir, art)),
                "missing report artifact: %s" % art)


if __name__ == "__main__":
    unittest.main()
