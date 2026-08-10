#!/usr/bin/env python3
"""score.py — offline scoring for law-citation-bench (stdlib only).

Each model is expected to return plain text in a simple, parseable format
(see README). We deliberately avoid NLP dependencies: character-level
overlap is the default similarity metric (no jieba / lxml), per the
offline-run constraint.

Scoring summary across the three tasks:
  T1 Citation Grounding : 0.7 * exact(law+article) + 0.3 * char-F1(key)
  T2 Retrieval           : Recall@5 (and MRR reported separately)
  T3 Hallucination Detect: Accuracy (1/0), with Macro-F1 aggregated later
"""
import re

from common import normalize_article, match_law

# --------------------------------------------------------------------------
# Similarity / parsing utilities
# --------------------------------------------------------------------------
def char_f1(a, b):
    sa, sb = set(a or ""), set(b or "")
    if not sa or not sb:
        return 0.0
    tp = len(sa & sb)
    prec = tp / len(sa)
    rec = tp / len(sb)
    if prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)


_ID_RE = re.compile(r"[A-Z][A-Z0-9_]+\d+(?:\.\d+)?_v1")
_LABEL_MAP = {
    "命中": "hit", "未命中": "miss", "篡改": "altered",
    "hit": "hit", "miss": "miss", "altered": "altered",
}

# Ordered label patterns. Critical ordering: ``未命中`` is matched BEFORE
# ``命中`` and ``命中`` uses a negative lookbehind so the ``命中`` substring
# inside ``未命中`` is NOT mistaken for "hit". CJK has no word boundaries,
# so a naive ``"命中" in text`` check mislabels every correct "未命中" answer.
_T3_PATTERNS = [
    (re.compile(r"篡\s*改"), "altered"),
    (re.compile(r"未\s*命中"), "miss"),
    (re.compile(r"(?<!未)命\s*中"), "hit"),
    (re.compile(r"\baltered\b", re.I), "altered"),
    (re.compile(r"\bmiss\b", re.I), "miss"),
    (re.compile(r"\bhit\b", re.I), "hit"),
]


def parse_t1(text):
    law = None
    article = None
    key = None
    for line in text.splitlines():
        if line.startswith("LAW:"):
            law = line[4:].strip()
        elif line.startswith("ARTICLE:"):
            article = line[8:].strip()
        elif line.startswith("KEY:"):
            key = line[4:].strip()
    if law is None and article is None:
        return None
    return {"law_code": law, "article_number": article, "key_sentence": key or ""}


def parse_t2(text):
    ids = []
    for tok in _ID_RE.findall(text):
        if tok not in ids:
            ids.append(tok)
    # also accept an explicit "ID: xxx" prefix
    for line in text.splitlines():
        if line.startswith("ID:"):
            tok = line[3:].strip()
            if _ID_RE.match(tok) and tok not in ids:
                ids.append(tok)
    return ids[:5]


def parse_t3(text):
    for pat, lab in _T3_PATTERNS:
        if pat.search(text):
            return lab
    return None


# --------------------------------------------------------------------------
# Per-record scoring
# --------------------------------------------------------------------------
def score_record(record, pred_text):
    task = record["task"]
    gold = record["gold"]
    if task == "T1":
        pred = parse_t1(pred_text)
        if pred is None:
            return {"score": 0.0, "hard": 0.0, "soft_f1": 0.0}
        # tolerant exact match: same answer in a different valid surface form
        # (第1条 / 第一条 / 1; VAT_LAW / 增值税法) must not be penalized.
        exact = (match_law(pred.get("law_code"), gold["law_code"]) and
                 normalize_article(pred.get("article_number")) ==
                 normalize_article(gold["article_number"]))
        f1 = char_f1(pred.get("key_sentence", ""), gold.get("key_sentence", ""))
        return {"score": 0.7 * (1.0 if exact else 0.0) + 0.3 * f1,
                "hard": 1.0 if exact else 0.0, "soft_f1": f1}
    if task == "T2":
        pred_ids = parse_t2(pred_text)
        gold_id = gold["relevant_ids"][0]
        if gold_id in pred_ids:
            rank = pred_ids.index(gold_id) + 1
            return {"score": 1.0, "recall@5": 1.0, "mrr": 1.0 / rank}
        return {"score": 0.0, "recall@5": 0.0, "mrr": 0.0}
    if task == "T3":
        pred_label = parse_t3(pred_text)
        correct = (pred_label == gold["label"])
        return {"score": 1.0 if correct else 0.0, "label": gold["label"],
                "pred": pred_label}
    raise ValueError("unknown task: %s" % task)


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------
def aggregate(records, scored):
    """Return per-task, per-difficulty, and task×difficulty aggregates.

    Output shape:
      {
        "overall": float,
        "tasks":      {T1:{n,mean}, T2:{n,mean,recall@5,mrr}, T3:{n,mean,macro_f1}},
        "difficulty": {easy:{n,mean}, medium:{...}, hard:{...}},
        "task_x_diff":{T1:{easy:{n,mean},...}, ...}   # M3 cross-breakdown
      }
    """
    by_task = {}
    by_diff = {}
    task_x_diff = {}
    for rec, res in zip(records, scored):
        t = rec["task"]
        d = rec["difficulty"]
        by_task.setdefault(t, []).append(res["score"])
        by_diff.setdefault(d, []).append(res["score"])
        task_x_diff.setdefault(t, {}).setdefault(d, []).append(res["score"])
    out = {"overall": _mean([s["score"] for s in scored]) if scored else 0.0,
           "tasks": {t: _stats(v) for t, v in by_task.items()},
           "difficulty": {d: _stats(v) for d, v in by_diff.items()},
           "task_x_diff": {t: {d: _stats(v) for d, v in task_x_diff[t].items()}
                           for t in task_x_diff}}
    # T2 extra metrics
    t2 = [(rec, res) for rec, res in zip(records, scored) if rec["task"] == "T2"]
    if t2:
        out["tasks"]["T2"]["recall@5"] = _mean([r["recall@5"] for _, r in t2])
        out["tasks"]["T2"]["mrr"] = _mean([r["mrr"] for _, r in t2])
    # T3 macro-F1 (3 classes: hit/miss/altered)
    t3 = [(rec, res) for rec, res in zip(records, scored) if rec["task"] == "T3"]
    if t3:
        out["tasks"]["T3"]["macro_f1"] = _macro_f1(t3)
    return out


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _stats(xs):
    return {"n": len(xs), "mean": _mean(xs)}


def _macro_f1(pairs):
    labels = ("hit", "miss", "altered")
    f1s = []
    for lab in labels:
        tp = fp = fn = 0
        for rec, res in pairs:
            gold = rec["gold"]["label"]
            pred = res.get("pred")
            if pred == lab and gold == lab:
                tp += 1
            elif pred == lab and gold != lab:
                fp += 1
            elif pred != lab and gold == lab:
                fn += 1
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)
    return _mean(f1s)


def t3_by_label(pairs):
    """Per-class accuracy for T3 (hit / miss / altered).

    ``pairs`` is a list of (record, scored) where record["task"] == "T3".
    Returns {label: {"n": int, "correct": int, "acc": float}}.
    """
    out = {lab: {"n": 0, "correct": 0, "acc": 0.0} for lab in ("hit", "miss", "altered")}
    for rec, res in pairs:
        lab = rec["gold"]["label"]
        if lab not in out:
            continue
        out[lab]["n"] += 1
        if res.get("pred") == lab:
            out[lab]["correct"] += 1
    for lab in out:
        n = out[lab]["n"]
        out[lab]["acc"] = (out[lab]["correct"] / n) if n else 0.0
    return out
