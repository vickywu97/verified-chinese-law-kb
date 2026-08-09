"""Smoke test for the Direction A benchmark prototype (benchmarks/law_citation_bench).

Runs under the repo's CI (``python -S -m unittest discover -s tests -t .``).
It exercises dataset generation + a baseline run without any network or
third-party dependency, keeping the benchmark self-verifying. Provider-adapter
tests mock the HTTP call so they verify wiring offline (no key, no tokens).
"""
import csv
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(os.path.dirname(HERE), "benchmarks", "law_citation_bench")
sys.path.insert(0, BENCH)

from build_dataset import build, DEFAULT_N  # noqa: E402
from run import run  # noqa: E402
from score import parse_t3, parse_t1, parse_t2  # noqa: E402
from adapters.openai_stub import PROVIDERS, resolve_provider  # noqa: E402


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


class ProviderAdapterTest(unittest.TestCase):
    def test_provider_presets_have_expected_endpoints(self):
        # base URLs must match the providers' OpenAI-compatible gateways
        self.assertEqual(
            PROVIDERS["qwen"]["base_url"],
            "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.assertEqual(PROVIDERS["deepseek"]["base_url"],
                         "https://api.deepseek.com/v1")
        self.assertEqual(PROVIDERS["zhipu"]["base_url"],
                         "https://open.bigmodel.cn/api/paas/v4")
        self.assertEqual(PROVIDERS["kimi"]["base_url"],
                         "https://api.moonshot.cn/v1")
        # every preset declares a default model + env-key name
        for name, p in PROVIDERS.items():
            self.assertIn("default_model", p)
            self.assertIn("env_key", p)

    def test_resolve_provider_requires_key(self):
        # No key anywhere -> clear RuntimeError naming the provider env var.
        with self.assertRaises(RuntimeError) as ctx:
            resolve_provider("qwen")
        self.assertIn("DASHSCOPE_API_KEY", str(ctx.exception))

    def test_resolve_provider_unknown(self):
        with self.assertRaises(ValueError):
            resolve_provider("not-a-provider")

    def test_adapter_hits_correct_endpoint_with_mock(self):
        # Verify the HTTP wiring against the qwen preset WITHOUT any real
        # network or the `requests` package: inject a fake `requests` module
        # into sys.modules so the adapter's lazy `import requests` resolves to it.
        import types
        fake_resp = mock.Mock()
        fake_resp.raise_for_status.return_value = None
        fake_resp.json.return_value = {
            "choices": [{"message": {"content": "LAW: VAT_LAW\nARTICLE: 第1条"}}]}
        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return fake_resp

        fake_requests = types.ModuleType("requests")
        fake_requests.post = fake_post
        saved = sys.modules.get("requests")
        sys.modules["requests"] = fake_requests
        try:
            with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test-123"}):
                adapter = resolve_provider("qwen")
                out = adapter.generate("cite article 1")
        finally:
            if saved is None:
                sys.modules.pop("requests", None)
            else:
                sys.modules["requests"] = saved
        self.assertEqual(captured["url"],
                         "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer sk-test-123")
        self.assertEqual(captured["json"]["model"], "qwen-plus")
        self.assertEqual(captured["json"]["messages"][0]["content"], "cite article 1")
        self.assertEqual(out, "LAW: VAT_LAW\nARTICLE: 第1条")
        # adapter name reflects provider/model for the leaderboard
        self.assertEqual(adapter.name, "qwen/qwen-plus")


class ParserRegressionTest(unittest.TestCase):
    """Regression tests for scorer parsers (offline, no network)."""

    def test_t3_no_substring_contamination(self):
        # The key bug: "未命中" contains "命中"; a naive check mislabels it.
        self.assertEqual(parse_t3("未命中"), "miss")
        self.assertEqual(parse_t3("该引用属于未命中"), "miss")
        self.assertEqual(parse_t3("命中"), "hit")
        self.assertEqual(parse_t3("篡改"), "altered")
        self.assertEqual(parse_t3("Hit"), "hit")
        self.assertEqual(parse_t3("该引用为篡改"), "altered")
        # prompts that echo all three options must not collapse to "hit"
        self.assertEqual(parse_t3("判断为：未命中"), "miss")
        self.assertIsNone(parse_t3("无法判断"))

    def test_t1_and_t2_parsers(self):
        t1 = parse_t1("LAW: VAT_LAW\nARTICLE: 第1条\nKEY: 在境内销售货物")
        self.assertEqual(t1["law_code"], "VAT_LAW")
        self.assertEqual(t1["article_number"], "第1条")
        self.assertIn("境内", t1["key_sentence"])
        self.assertIsNone(parse_t1("完全无关的回答"))
        ids = parse_t2("VAT_LAW_1_v1\nVAT_LAW_2_v1\nVAT_LAW_3_v1")
        self.assertEqual(ids, ["VAT_LAW_1_v1", "VAT_LAW_2_v1", "VAT_LAW_3_v1"])
        self.assertEqual(parse_t2("ID: CIVIL_CODE_5_v1"), ["CIVIL_CODE_5_v1"])


if __name__ == "__main__":
    unittest.main()
