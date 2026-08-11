#!/usr/bin/env python3
"""vendor_kb_index.py — snapshot the verified statutes into this benchmark's
self-contained ground-truth file ``kb/kb_index.jsonl``.

The benchmark is published as a STANDALONE repository: it ships with a vendored
snapshot of the verified-chinese-law-kb ground truth so it runs fully offline
(offline baselines + scoring) without cloning the parent KB. Re-run this script
(from a checkout that also has the KB's ``modules/``) to refresh the snapshot.

Usage:
    python3 tools/vendor_kb_index.py                 # default: ../../modules
    python3 tools/vendor_kb_index.py --modules /path/to/kb/modules
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
# tools/ -> law-citation-bench/ -> repo root
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
DEFAULT_MODULES = os.path.join(REPO_ROOT, "modules")
OUT_PATH = os.path.join(HERE, "..", "kb", "kb_index.jsonl")


def main():
    ap = argparse.ArgumentParser(description="Vendor verified statutes into kb/kb_index.jsonl")
    ap.add_argument("--modules", default=DEFAULT_MODULES,
                    help="verified-chinese-law-kb modules/ directory")
    ap.add_argument("--out", default=OUT_PATH, help="output kb index path")
    args = ap.parse_args()

    if not os.path.isdir(args.modules):
        raise SystemExit("modules dir not found: %s" % args.modules)

    records = []
    for mod in sorted(os.listdir(args.modules)):
        path = os.path.join(args.modules, mod, "statutes.jsonl")
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

    if not records:
        raise SystemExit("no verified statutes found under %s" % args.modules)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print("vendored %d verified statutes -> %s"
          % (len(records), os.path.normpath(args.out)))


if __name__ == "__main__":
    main()
