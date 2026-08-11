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
import sys
import time

from .base import ModelAdapter


# OpenAI-compatible provider presets. Add more here as needed.
#   timeout        : per-request timeout (s); reasoning models need generous values
#   disable_thinking: send {"thinking": {"type": "disabled"}} (kimi-k2 default ON)
PROVIDERS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "env_key": "LAW_BENCH_OPENAI_KEY",
        "timeout": 120,
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "env_key": "DASHSCOPE_API_KEY",
        "timeout": 120,
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY",
        "timeout": 120,
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "env_key": "ZHIPU_API_KEY",
        "timeout": 120,
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "kimi-k2.6",
        "env_key": "MOONSHOT_API_KEY",
        "timeout": 300,
        "disable_thinking": True,
        # Moonshot/Kimi congests under burst; give the per-request retry more
        # headroom so a 429 slides through the rolling window instead of
        # failing the whole question.
        "max_retries": 8,
    },
}

# Fallback generic env var checked after the provider-specific one.
GENERIC_ENV_KEY = "LAW_BENCH_API_KEY"


class OpenAIAdapter(ModelAdapter):
    """Adapter for any OpenAI-compatible chat completions API."""

    name = "openai-compatible"

    def __init__(self, api_key, model, base_url="https://api.openai.com/v1",
                 name=None, timeout=120, extra_body=None, max_retries=5):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.name = name or ("%s (%s)" % (model, base_url))
        self.timeout = timeout
        self.extra_body = extra_body or {}
        self.max_retries = max_retries
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
        from requests.exceptions import (
            ReadTimeout, ConnectTimeout, ConnectionError, ChunkedEncodingError,
            HTTPError,
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        payload.update(self.extra_body)  # e.g. {"thinking": {"type": "disabled"}}
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    self.base_url + "/chat/completions",
                    headers={"Authorization": "Bearer %s" % self.api_key},
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except HTTPError as e:
                last_err = e
                status = getattr(getattr(e, "response", None), "status_code", None)
                # 429 (rate-limited) and 5xx (transient server) are retryable;
                # 4xx (bad request / auth) are permanent -> raise at once.
                retryable = status in (429, 500, 502, 503, 504)
                if attempt < self.max_retries and retryable:
                    backoff = _retry_after(e) or (5 * 2 ** (attempt - 1))
                    sys.stderr.write(
                        "  [warn] %s attempt %d/%d HTTP %s; retry in %ds\n"
                        % (self.model, attempt, self.max_retries, status, backoff))
                    time.sleep(backoff)
                    continue
                raise  # permanent error or out of retries
            except (ReadTimeout, ConnectTimeout, ConnectionError,
                    ChunkedEncodingError) as e:
                last_err = e
                if attempt < self.max_retries:
                    backoff = 5 * 2 ** (attempt - 1)  # 5s, 10s, 20s, ...
                    sys.stderr.write(
                        "  [warn] %s attempt %d/%d failed (%s); retry in %ds\n"
                        % (self.model, attempt, self.max_retries,
                           type(e).__name__, backoff))
                    time.sleep(backoff)
                    continue
        # surface the last transient error after exhausting retries
        raise last_err


def _retry_after(exc):
    """Return Retry-After seconds from an HTTPError response, capped at 60."""
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    ra = resp.headers.get("Retry-After")
    if not ra:
        return None
    try:
        return min(int(ra), 60)
    except ValueError:
        return None


def resolve_provider(provider, api_key=None, model_name=None, base_url=None,
                      timeout=None):
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
    extra_body = {}
    if preset.get("disable_thinking"):
        extra_body["thinking"] = {"type": "disabled"}
    return OpenAIAdapter(
        api_key=key,
        model=model,
        base_url=(base_url or preset["base_url"]),
        name="%s/%s" % (provider, model),
        timeout=(timeout or preset.get("timeout", 120)),
        extra_body=extra_body,
        max_retries=preset.get("max_retries", 5),
    )
