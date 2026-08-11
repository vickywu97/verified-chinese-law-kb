"""adapters package — pluggable model adapters for law-citation-bench.

All adapters implement ``generate(prompt) -> str`` so the runner is agnostic
to the underlying model. The scorer only needs the returned text in the
documented format.
"""
from .base import ModelAdapter
from .dummy import AlwaysFirstBaseline, RandomBaseline
from .openai_stub import OpenAIAdapter

__all__ = ["ModelAdapter", "AlwaysFirstBaseline", "RandomBaseline", "OpenAIAdapter"]
