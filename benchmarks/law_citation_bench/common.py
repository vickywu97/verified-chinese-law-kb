"""common.py — shared helpers for the law-citation-bench prototype.

Offline / stdlib only. Loads verified statutes from the parent repo's
``modules/`` directory (the ground truth) and exposes the law-name map.
"""
import json
import os

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
