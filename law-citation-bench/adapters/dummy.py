"""dummy.py — calibration baselines (no real model, fully offline).

These baselines prove the benchmark can separate good from bad models:
a random / constant guess should score far below a competent legal model.
"""
import random

from .base import ModelAdapter


class AlwaysFirstBaseline(ModelAdapter):
    """Always answers with the first KB article / a constant label.

    T1 -> cites KB[0]; T2 -> Top-5 = first 5 ids; T3 -> always "命中".
    Near-zero T1/T2 score; T3 score ~ fraction of gold that is "hit".
    """
    name = "always-first-baseline"

    def __init__(self, kb):
        if not kb:
            raise ValueError("kb pool is empty")
        self.kb = kb

    def generate(self, prompt):
        if prompt.startswith("[T1]"):
            a = self.kb[0]
            return "LAW: %s\nARTICLE: %s\nKEY: %s" % (
                a["law_code"], a["article_number"], a["content"][:20])
        if prompt.startswith("[T2]"):
            ids = "\n".join("ID: %s" % r["id"] for r in self.kb[:5])
            return ids
        # T3
        return "命中"


class RandomBaseline(ModelAdapter):
    """Random plausible answer per query (seeded for reproducibility)."""
    name = "random-baseline"

    def __init__(self, kb, seed=20260809):
        if not kb:
            raise ValueError("kb pool is empty")
        self.kb = kb
        self.rng = random.Random(seed)
        self.labels = ["命中", "未命中", "篡改"]

    def generate(self, prompt):
        if prompt.startswith("[T1]"):
            a = self.rng.choice(self.kb)
            return "LAW: %s\nARTICLE: %s\nKEY: %s" % (
                a["law_code"], a["article_number"], a["content"][:20])
        if prompt.startswith("[T2]"):
            sample = self.rng.sample(self.kb, min(5, len(self.kb)))
            return "\n".join("ID: %s" % r["id"] for r in sample)
        return self.rng.choice(self.labels)
