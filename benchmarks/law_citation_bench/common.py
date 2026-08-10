"""common.py — shared helpers for the law-citation-bench prototype.

Offline / stdlib only. Loads verified statutes from the parent repo's
``modules/`` directory (the ground truth) and exposes the law-name map.
"""
import json
import os
import re

# law_code -> human-readable Chinese law name (used in generated queries)
LAW_NAMES = {
    "CIVIL_CODE": "民法典",
    "CRIMINAL_LAW": "刑法",
    "COMPANY_LAW": "公司法",
    "TAX_ADMIN_LAW": "税收征收管理法",
    "VAT_LAW": "增值税法",
    "EIT_LAW": "企业所得税法",
    "IIT_LAW": "个人所得税法",
    "PATENT_LAW": "专利法",
}
# reverse map: Chinese name -> law_code (a model may answer with either form)
NAME_TO_CODE = {v: k for k, v in LAW_NAMES.items()}


# --------------------------------------------------------------------------
# Format-tolerant normalization (fairness: same answer, different valid format
# must not be penalized). Pure syntactic, no semantic ambiguity.
# --------------------------------------------------------------------------
_CN_NUM = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    "十": 10, "百": 100, "千": 1000,
}


def cn_to_int(text):
    """Convert a short Chinese numeral (十/百/千 range) to int. Returns None
    if it cannot be parsed as a pure Chinese numeral."""
    if not text:
        return None
    total, cur = 0, 0
    for ch in text:
        if ch in "零〇一二两三四五六七八九":
            cur = _CN_NUM[ch]
        elif ch == "十":
            total += (cur if cur else 1) * 10
            cur = 0
        elif ch == "百":
            total += (cur if cur else 1) * 100
            cur = 0
        elif ch == "千":
            total += (cur if cur else 1) * 1000
            cur = 0
        else:
            return None
    return total + cur


def normalize_article(art):
    """Normalize an article reference to an int regardless of surface form:
    '第1条' / '第一条' / '1' / '第1260条' all -> 1 / 1260. Returns None if
    no article number can be extracted."""
    if art is None:
        return None
    s = art.strip()
    # keep Arabic digits and CJK numerals only; drop 第/条/款/项/空格
    s = re.sub(r"[^一二三四五六七八九十百千零〇0-9]", "", s)
    if not s:
        return None
    if re.fullmatch(r"[0-9]+", s):
        return int(s)
    return cn_to_int(s)


def match_law(pred_law, gold_law_code):
    """True if ``pred_law`` denotes the same law as ``gold_law_code``, whether
    the model answered with the code (VAT_LAW) or the Chinese name (增值税法)."""
    if not pred_law:
        return False
    if pred_law == gold_law_code:
        return True
    if LAW_NAMES.get(gold_law_code) == pred_law:
        return True
    if NAME_TO_CODE.get(pred_law) == gold_law_code:
        return True
    return False

# Path resolution: this file lives at <repo>/benchmarks/law_citation_bench/common.py
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
MODULES_DIR = os.path.join(REPO_ROOT, "modules")


def load_statutes(modules_dir=MODULES_DIR):
    """Load every verified statute from ``modules/*/statutes.jsonl``.

    Only records with ``verification_status == "verified"`` are treated as
    ground truth. Returns a list of dict records (order is stable: sorted by
    module name then file order).
    """
    records = []
    if not os.path.isdir(modules_dir):
        raise FileNotFoundError("modules dir not found: %s" % modules_dir)
    for mod_name in sorted(os.listdir(modules_dir)):
        path = os.path.join(modules_dir, mod_name, "statutes.jsonl")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("verification_status") != "verified":
                    continue
                records.append(rec)
    return records


def law_name(law_code):
    return LAW_NAMES.get(law_code, law_code)


def split_clauses(text):
    """Split Chinese text into clauses on common sentence punctuation."""
    parts = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in "。；":
            parts.append(buf.strip())
            buf = ""
    if buf.strip():
        parts.append(buf.strip())
    return [p for p in parts if p]


def first_clause(text):
    clauses = split_clauses(text)
    if not clauses:
        return text.strip()
    # drop a leading purpose clause ("为了…制定本法") if present
    first = clauses[0]
    if first.startswith("为了") and ("制定本法" in first or "制定本条例" in first):
        if len(clauses) > 1:
            return clauses[1]
    return first


def max_article_number_per_law(records):
    """Map law_code -> largest integer part of article_sort_key (for out-of-range cites)."""
    out = {}
    for r in records:
        sk = r.get("article_sort_key")
        if isinstance(sk, (int, float)):
            key = int(sk)
            out[r["law_code"]] = max(out.get(r["law_code"], 0), key)
    return out
