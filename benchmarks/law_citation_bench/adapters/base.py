"""base.py — adapter interface."""
from abc import ABC, abstractmethod


class ModelAdapter(ABC):
    """Unified interface for any model behind the benchmark.

    The runner calls ``generate(prompt)`` and feeds the returned text
    straight to the scorer. Implementations must emit the formats documented
    in README (LAW:/ARTICLE:/KEY: for T1, id lists for T2, a label for T3).
    """

    name = "model-adapter"

    @abstractmethod
    def generate(self, prompt):
        """Return the model's textual answer for ``prompt``."""
        raise NotImplementedError

    def close(self):
        """Optional cleanup (e.g. close a client)."""
        return None
