"""openai_stub.py — template for a real API adapter (NOT used by default).

Demonstrates the pluggability point in the design doc: scoring is decoupled
from the model. Wire this up with a user-supplied key to run real models;
the benchmark stays offline for truth comparison, scoring, and reporting.
"""
from .base import ModelAdapter


class OpenAIAdapter(ModelAdapter):
    """Adapter for OpenAI-compatible chat completions APIs.

    Usage (user provides key + model; never committed):
        adapter = OpenAIAdapter(api_key=..., base_url=..., model="gpt-4o")
        text = adapter.generate(prompt)
    """
    name = "openai-compatible"

    def __init__(self, api_key, model, base_url="https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        # Lazy import so the stdlib-only default path never requires `requests`.
        try:
            import requests  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "openai adapter needs `requests`; install it in an isolated venv. "
                "Default benchmark runs offline without it."
            )

    def generate(self, prompt):
        import requests
        resp = requests.post(
            self.base_url + "/chat/completions",
            headers={"Authorization": "Bearer %s" % self.api_key},
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}]},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
