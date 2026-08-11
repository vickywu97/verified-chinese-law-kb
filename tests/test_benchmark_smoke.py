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
BENCH = os.path.join(os.path.dirname(HERE), "law-citation-bench")
sys.path.insert(0, BENCH)

from build_dataset import build, DEFAULT_N  # noqa: E402
from run import (run, run_model, load_preds, merge_runs,  # noqa: E402
                  build_prompt, set_prompt_version)
from score import (parse_t3, parse_t1, parse_t2, t3_by_label,  # noqa: E402
                   score_record, normalize_article, match_law,
                   normalize_t2_id)
from adapters.openai_stub import PROVIDERS, resolve_provider  # noqa: E402
from adapters import RandomBaseline, AlwaysFirstBaseline  # noqa: E402
from common import load_statutes  # noqa: E402


def tiny_dataset():
    """Build a small deterministic dataset and return (path, rows)."""
    rows, _ = build(12, 20260809)
    tmp = tempfile.mktemp(suffix=".jsonl")
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return tmp, rows


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
        fake_requests.__path__ = []
        fake_requests.post = fake_post
        fake_exc = types.ModuleType("requests.exceptions")
        for nm in ("ReadTimeout", "ConnectTimeout", "ConnectionError",
                   "ChunkedEncodingError", "HTTPError"):
            setattr(fake_exc, nm, type(nm, (Exception,), {}))
        fake_requests.exceptions = fake_exc
        saved = sys.modules.get("requests")
        saved_exc = sys.modules.get("requests.exceptions")
        sys.modules["requests"] = fake_requests
        sys.modules["requests.exceptions"] = fake_exc
        try:
            with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test-123"}):
                adapter = resolve_provider("qwen")
                out = adapter.generate("cite article 1")
        finally:
            if saved is None:
                sys.modules.pop("requests", None)
            else:
                sys.modules["requests"] = saved
            if saved_exc is None:
                sys.modules.pop("requests.exceptions", None)
            else:
                sys.modules["requests.exceptions"] = saved_exc
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

    def test_t2_id_normalization_fairness(self):
        # Syntactic variants of the SAME article must normalize to the
        # canonical KB id so a correct answer is not unfairly penalized.
        self.assertEqual(parse_t2("CIVIL_CODE_ART_654_v1"),
                         ["CIVIL_CODE_654_v1"])
        self.assertEqual(parse_t2("CIVIL_CODE_ARTICLE_331_v1"),
                         ["CIVIL_CODE_331_v1"])
        self.assertEqual(parse_t2("COMP_LAW_37_v1"),
                         ["COMPANY_LAW_37_v1"])
        # trailing _v1 optional and a CJK suffix after the id are tolerated
        self.assertEqual(parse_t2("VAT_LAW_1_v1：民法典第123条"),
                         ["VAT_LAW_1_v1"])
        # a model-invented / wrong code is NOT aliased -> stays a miss
        self.assertEqual(parse_t2("CEN_LAW_6_v1"), ["CEN_LAW_6_v1"])
        self.assertEqual(normalize_t2_id("CIVIL_CODE_ART_654_v1"),
                         "CIVIL_CODE_654_v1")

    def test_article_number_normalization(self):
        # same article, different valid surface forms collapse to one int
        self.assertEqual(normalize_article("第1条"), 1)
        self.assertEqual(normalize_article("第一条"), 1)
        self.assertEqual(normalize_article("1"), 1)
        self.assertEqual(normalize_article("第1260条"), 1260)
        self.assertEqual(normalize_article("第一千二百六十条"), 1260)
        self.assertIsNone(normalize_article("无条文"))

    def test_law_match_accepts_code_or_name(self):
        self.assertTrue(match_law("VAT_LAW", "VAT_LAW"))
        self.assertTrue(match_law("增值税法", "VAT_LAW"))
        self.assertFalse(match_law("企业所得税法", "VAT_LAW"))

    def test_t1_tolerant_exact_match(self):
        # gold uses code + 第N条; a model answering with the Chinese name and
        # a Chinese numeral must still score an exact (hard) match.
        rec = {"task": "T1", "gold": {"law_code": "VAT_LAW",
                                       "article_number": "第1条",
                                       "key_sentence": "在境内销售货物"}}
        good = "LAW: 增值税法\nARTICLE: 第一条\nKEY: 在境内销售货物"
        bad = "LAW: 企业所得税法\nARTICLE: 第1条\nKEY: 在境内销售货物"
        self.assertEqual(score_record(rec, good)["hard"], 1.0)
        self.assertEqual(score_record(rec, bad)["hard"], 0.0)


class PromptVersionTest(unittest.TestCase):
    """T3 prompt variants (v1 vs v2) must serialize deterministically and
    v2 must embed the non-leaking per-law article counts + label options."""

    def test_v1_prompt_is_legacy_form(self):
        rec = {"task": "T3", "query": "根据《增值税法》第1条的规定：……"}
        self.assertEqual(
            build_prompt(rec, "v1"),
            "[T3] 根据《增值税法》第1条的规定：……\n"
            "判断该引用属于哪一类：命中 / 未命中 / 篡改")

    def test_v2_prompt_embeds_counts_and_options(self):
        rec = {"task": "T3", "query": "根据《增值税法》第1条的规定：……"}
        p = build_prompt(rec, "v2")
        # public, non-leaking article counts present (consistent with the
        # dataset's out-of-range '未命中' generation)
        self.assertIn("《增值税法》38条", p)
        self.assertIn("《民法典》1260条", p)
        # the three labels + the explicit instruction to output one of them
        for lab in ("命中", "篡改", "未命中"):
            self.assertIn(lab, p)
        self.assertIn("只输出一个标签", p)
        # the actual query text is included verbatim
        self.assertIn("根据《增值税法》第1条的规定：……", p)

    def test_set_prompt_version_rejects_bad_value(self):
        with self.assertRaises(ValueError):
            set_prompt_version("v9")
        set_prompt_version("v1")
        set_prompt_version("v2")


class T3BreakdownTest(unittest.TestCase):
    def test_t3_by_label_structure(self):
        pairs = [
            ({"task": "T3", "gold": {"label": "hit"}}, {"pred": "hit", "score": 1.0}),
            ({"task": "T3", "gold": {"label": "hit"}}, {"pred": "miss", "score": 0.0}),
            ({"task": "T3", "gold": {"label": "miss"}}, {"pred": "miss", "score": 1.0}),
            ({"task": "T3", "gold": {"label": "altered"}}, {"pred": "altered", "score": 1.0}),
        ]
        b = t3_by_label(pairs)
        self.assertEqual(b["hit"], {"n": 2, "correct": 1, "acc": 0.5})
        self.assertEqual(b["miss"], {"n": 1, "correct": 1, "acc": 1.0})
        self.assertEqual(b["altered"], {"n": 1, "correct": 1, "acc": 1.0})


class PipelineTest(unittest.TestCase):
    """save-preds + offline merge round-trip (no network, no key)."""

    def test_save_preds_roundtrip(self):
        ds, rows = tiny_dataset()
        kb = load_statutes()
        a = RandomBaseline(kb)
        preds_path = tempfile.mktemp(suffix=".jsonl")
        run_model(a, rows, kb, 0, preds_path)
        name, preds = load_preds(preds_path)
        self.assertEqual(name, a.name)
        self.assertEqual(len(preds), len(rows))
        self.assertTrue(all("pred_text" in p and "qid" in p for p in preds))
        self.assertEqual({p["qid"] for p in preds}, {r["qid"] for r in rows})

    def test_offline_merge_two_saved(self):
        ds, rows = tiny_dataset()
        kb = load_statutes()
        p1 = tempfile.mktemp(suffix=".jsonl")
        p2 = tempfile.mktemp(suffix=".jsonl")
        run_model(RandomBaseline(kb), rows, kb, 0, p1)
        run_model(AlwaysFirstBaseline(kb), rows, kb, 0, p2)
        out = tempfile.mktemp(suffix=".csv")
        out_dir = os.path.dirname(out)
        merge_runs([p1, p2], "all", out, ds, rows)
        with open(os.path.join(out_dir, "leaderboard.json"), encoding="utf-8") as fh:
            payload = json.load(fh)
        names = {m["model"] for m in payload["models"]}
        # both saved baselines present, no double-counting (merge skips recompute)
        self.assertEqual(names, {"random-baseline", "always-first-baseline"})
        for m in payload["models"]:
            b = m["t3_by_label"]
            tot = sum(b[l]["n"] for l in ("hit", "miss", "altered"))
            self.assertEqual(tot, m["tasks"]["T3"]["n"])

    def test_merge_recomputes_baselines_with_nonzero_score(self):
        # Regression: baselines are recomputed in merge mode WITHOUT a saved
        # file (save_path=None). A bug once gated generation behind save_path,
        # scoring baselines as all-empty (0.0). They must score > 0.
        ds, rows = tiny_dataset()
        kb = load_statutes()
        # a synthetic saved model file (not a baseline) so merge recomputes them
        pf = tempfile.mktemp(suffix=".jsonl")
        with open(pf, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps({
                    "model": "fake/model", "qid": r["qid"], "task": r["task"],
                    "law_code": r["law_code"], "difficulty": r["difficulty"],
                    "source_article_id": r.get("source_article_id"),
                    "pred_text": "ignored",
                }, ensure_ascii=False) + "\n")
        out = tempfile.mktemp(suffix=".csv")
        out_dir = os.path.dirname(out)
        merge_runs([pf], "all", out, ds, rows)
        with open(os.path.join(out_dir, "leaderboard.json"), encoding="utf-8") as fh:
            payload = json.load(fh)
        by_name = {m["model"]: m for m in payload["models"]}
        self.assertIn("random-baseline", by_name)
        self.assertIn("always-first-baseline", by_name)
        # both baselines must have actually run (non-zero overall)
        self.assertGreater(by_name["random-baseline"]["overall"], 0.0)
        self.assertGreater(by_name["always-first-baseline"]["overall"], 0.0)


class ResilienceTest(unittest.TestCase):
    """run_model must survive per-question API failures and support resume."""

    class _FakeAdapter:
        name = "fake/canned"

        def __init__(self, fail_indices=()):
            self._i = 0
            self._fail = set(fail_indices)

        def generate(self, prompt):
            idx = self._i
            self._i += 1
            if idx in self._fail:
                raise RuntimeError("simulated API timeout at call %d" % idx)
            return "pred-%d" % idx

    def test_per_question_failure_does_not_abort_run(self):
        ds, rows = tiny_dataset()
        kb = load_statutes()
        # fail the first and the last call; the rest must still be recorded.
        n = len(rows)
        adapter = self._FakeAdapter(fail_indices={0, n - 1})
        preds_path = tempfile.mktemp(suffix=".jsonl")
        model = run_model(adapter, rows, kb, 0, preds_path)
        name, preds = load_preds(preds_path)
        self.assertEqual(len(preds), n)
        empties = [p for p in preds if p["pred_text"] == ""]
        self.assertEqual(len(empties), 2)  # the two failed calls
        oks = [p for p in preds if p["pred_text"] != ""]
        self.assertEqual(len(oks), n - 2)
        self.assertTrue(all(p["pred_text"].startswith("pred-") for p in oks))
        # the run completes (n equals dataset size, overall is finite)
        self.assertEqual(model["n"], n)

    def test_resume_skips_done_and_appends_no_duplicates(self):
        ds, rows = tiny_dataset()
        kb = load_statutes()
        preds_path = tempfile.mktemp(suffix=".jsonl")
        # first (full) run writes all predictions
        run_model(self._FakeAdapter(), rows, kb, 0, preds_path)
        first = load_preds(preds_path)[1]
        first_count = len(first)

        # simulate a crash: keep only the first 3 rows, discard the rest.
        name, preds = load_preds(preds_path)
        with open(preds_path, "w", encoding="utf-8") as fh:
            for p in preds[:3]:
                fh.write(json.dumps({"model": name, **p}, ensure_ascii=False) + "\n")

        # resume must re-run only the missing qids and append (no duplicates).
        run_model(self._FakeAdapter(), rows, kb, 0, preds_path, resume=True)
        _, preds2 = load_preds(preds_path)
        self.assertEqual(len(preds2), first_count)
        qids = [p["qid"] for p in preds2]
        self.assertEqual(len(set(qids)), len(qids))  # no duplicate qids

    def test_resume_reruns_empty_predictions(self):
        # A rate-limit burst leaves some qids with EMPTY pred_text (recorded
        # failures). --resume must treat those as incomplete and re-run them,
        # instead of skipping them as "done" — so no manual empty-filter step.
        ds, rows = tiny_dataset()
        kb = load_statutes()
        preds_path = tempfile.mktemp(suffix=".jsonl")
        run_model(self._FakeAdapter(), rows, kb, 0, preds_path)  # all good
        name, preds = load_preds(preds_path)
        # corrupt: keep first 3 good, turn next 3 into EMPTY, drop the rest 6.
        with open(preds_path, "w", encoding="utf-8") as fh:
            for p in preds[:3]:
                fh.write(json.dumps({"model": name, **p}, ensure_ascii=False) + "\n")
            for p in preds[3:6]:
                p2 = dict(p)
                p2["pred_text"] = ""
                fh.write(json.dumps({"model": name, **p2}, ensure_ascii=False) + "\n")
        # resume re-runs the 3 empties + 6 missing -> all 12 good, no dupes.
        run_model(self._FakeAdapter(), rows, kb, 0, preds_path, resume=True)
        _, preds2 = load_preds(preds_path)
        self.assertEqual(len(preds2), len(rows))
        qids = [p["qid"] for p in preds2]
        self.assertEqual(len(set(qids)), len(qids))  # no duplicates
        empties = [p for p in preds2 if not p.get("pred_text")]
        self.assertEqual(len(empties), 0)  # empties were re-run


class ProviderAdapterRetryTest(unittest.TestCase):
    """The adapter MUST retry on rate-limit (429) / 5xx HTTP errors.

    Regression guard for the bug where ``resp.raise_for_status()`` raised
    ``HTTPError`` (what a 429 returns) but the retry loop only caught socket
    timeouts — so every rate-limited request failed instantly and was written
    as an empty prediction.
    """

    def _install(self, post_fn):
        import types
        import sys
        from unittest import mock

        class FakeHTTPError(Exception):
            def __init__(self, response=None):
                super().__init__("http")
                self.response = response

        exc = types.ModuleType("requests.exceptions")
        for nm in ("ReadTimeout", "ConnectTimeout", "ConnectionError",
                   "ChunkedEncodingError"):
            setattr(exc, nm, type(nm, (Exception,), {}))
        exc.HTTPError = FakeHTTPError

        fake = types.ModuleType("requests")
        fake.__path__ = []
        fake.post = post_fn
        fake.exceptions = exc

        saved = sys.modules.get("requests")
        saved_exc = sys.modules.get("requests.exceptions")
        sys.modules["requests"] = fake
        sys.modules["requests.exceptions"] = exc
        self._saved = saved
        self._saved_exc = saved_exc
        self._FakeHTTPError = FakeHTTPError
        self._mock = mock
        return saved

    def _restore(self):
        import sys
        saved = self._saved
        if saved is None:
            sys.modules.pop("requests", None)
        else:
            sys.modules["requests"] = saved
        if self._saved_exc is None:
            sys.modules.pop("requests.exceptions", None)
        else:
            sys.modules["requests.exceptions"] = self._saved_exc

    def _resp(self, status, retry_after=None, content="OK"):
        resp = self._mock.Mock()
        resp.status_code = status
        resp.headers = {"Retry-After": str(retry_after)} if retry_after else {}
        if 200 <= status < 300:
            resp.raise_for_status.return_value = None
            resp.json.return_value = {
                "choices": [{"message": {"content": content}}]}
        else:
            resp.raise_for_status.side_effect = self._FakeHTTPError(resp)
        return resp

    def test_retries_on_429_then_succeeds(self):
        import sys
        calls = {"n": 0}

        def post(url, headers=None, json=None, timeout=None):
            i = calls["n"]
            calls["n"] += 1
            if i < 2:
                return self._resp(429, retry_after=0)
            return self._resp(200)

        saved = self._install(post)
        try:
            from adapters.openai_stub import OpenAIAdapter
            a = OpenAIAdapter(api_key="x", model="m", base_url="http://x/v1",
                              name="t/t", max_retries=5)
            out = a.generate("hi")
        finally:
            self._restore()
        self.assertEqual(out, "OK")
        self.assertEqual(calls["n"], 3)  # two 429s retried, then success

    def test_4xx_is_not_retried(self):
        import sys
        calls = {"n": 0}

        def post(url, headers=None, json=None, timeout=None):
            calls["n"] += 1
            return self._resp(400)

        saved = self._install(post)
        try:
            from adapters.openai_stub import OpenAIAdapter
            a = OpenAIAdapter(api_key="x", model="m", base_url="http://x/v1",
                              name="t/t", max_retries=5)
            with self.assertRaises(Exception):
                a.generate("hi")
        finally:
            self._restore()
        self.assertEqual(calls["n"], 1)  # permanent error, no retry

    def test_honors_retry_after_header(self):
        import sys
        import time
        slept = []
        real_sleep = time.sleep
        time.sleep = lambda s: slept.append(s)
        calls = {"n": 0}

        def post(url, headers=None, json=None, timeout=None):
            i = calls["n"]
            calls["n"] += 1
            if i < 1:
                return self._resp(429, retry_after=3)
            return self._resp(200)

        saved = self._install(post)
        try:
            from adapters.openai_stub import OpenAIAdapter
            a = OpenAIAdapter(api_key="x", model="m", base_url="http://x/v1",
                              name="t/t", max_retries=5)
            out = a.generate("hi")
        finally:
            time.sleep = real_sleep
            self._restore()
        self.assertEqual(out, "OK")
        self.assertIn(3, slept)  # waited the server-specified Retry-After


if __name__ == "__main__":
    unittest.main()
