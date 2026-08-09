"""openai_stub.py — real-model adapter via OpenAI-compatible chat completions.

The four Chinese providers available to the user
(阿里/Qwen DashScope, DeepSeek, 智谱/GLM, Kimi/Moonshot) all expose an
OpenAI-compatible ``/v1/chat/completions`` endpoint, so a single adapter serves
them with provider presets (base URL + default model + env-key name).

Key resolution order: ``--api-key`` -> provider env var -> generic
``LAW_BENCH_API_KEY``. The key is never committed.

Usage (user supplies the key):
    from adapters.openai_stub import resolve_provider
    adapter = resolve_provider("qwen", api_key="sk-...")
    text = adapter.generate(prompt)
"""
import os

from .base import ModelAdapter


# OpenAI-compatible provider presets. Add more here as needed.
PROVIDERS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "env_key": "LAW_BENCH_OPENAI_KEY",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "env_key": "DASHSCOPE_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "env_key": "ZHIPU_API_KEY",
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "env_key": "MOONSHOT_API_KEY",
    },
}

# Fallback generic env var checked after the provider-specific one.
GENERIC_ENV_KEY = "LAW_BENCH_API_KEY"


class OpenAIAdapter(ModelAdapter):
    """Adapter for any OpenAI-compatible chat completions API."""

    name = "openai-compatible"

    def __init__(self, api_key, model, base_url="https://api.openai.com/v1",
                 name=None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.name = name or ("%s (%s)" % (model, base_url))
        # Lazy import so the stdlib-only default path never requires `requests`.
        try:
            import requests  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "real-model adapter needs `requests`; install it in an isolated "
                "venv. Default benchmark runs offline without it."
            )

    def generate(self, prompt):
        import requests
        resp = requests.post(
            self.base_url + "/chat/completions",
            headers={"Authorization": "Bearer %s" % self.api_key},
            json={"model": self.model,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def resolve_provider(provider, api_key=None, model_name=None, base_url=None):
    """Return an ``OpenAIAdapter`` for a named provider preset.

    Key resolution order: explicit ``api_key`` -> provider env var ->
    generic ``LAW_BENCH_API_KEY``. Raises ``RuntimeError`` (clear message) if
    no key is found, and ``ValueError`` for an unknown provider.
    """
    if provider not in PROVIDERS:
        raise ValueError("unknown provider %r; choose from: %s"
                         % (provider, ", ".join(sorted(PROVIDERS))))
    preset = PROVIDERS[provider]
    key = (api_key
           or os.environ.get(preset["env_key"])
           or os.environ.get(GENERIC_ENV_KEY))
    if not key:
        raise RuntimeError(
            "provider %r needs an API key: pass --api-key or set %s "
            "(or the generic %s)" % (provider, preset["env_key"], GENERIC_ENV_KEY))
    model = model_name or preset["default_model"]
    return OpenAIAdapter(
        api_key=key,
        model=model,
        base_url=(base_url or preset["base_url"]),
        name="%s/%s" % (provider, model),
    )
