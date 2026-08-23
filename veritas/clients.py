"""
Multi-provider LLM client with disk caching, strict-JSON coercion, and telemetry.

This is the one place every node talks to a model through. Centralising it here
means caching, retries, and cost tracking are applied uniformly instead of
reimplemented per node.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "llm"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# USD per 1M tokens (input, output). Approximate published rates; used only
# for the benchmark's relative cost comparison, not billing.
RATE_TABLE = {
    "gemma4:31b": (0.10, 0.40),
    "gpt-oss:120b": (0.10, 0.50),
    "llama-3.3-70b": (0.13, 0.40),
}


_RETRY_DELAY_RE = re.compile(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s")


def _retry_delay_seconds(e: Exception, attempt: int, cap: float = 65.0) -> float:
    """Honor the API's own rate-limit retry hint (e.g. Gemini free-tier 429s carry a
    retryDelay) instead of a blind exponential backoff that's far too short for a
    per-minute quota. Falls back to exponential backoff when no hint is present."""
    match = _RETRY_DELAY_RE.search(str(e))
    if match:
        return min(float(match.group(1)) + 1, cap)
    return min(2**attempt, 8)


class NodeParseError(Exception):
    """Raised when a node's LLM response can't be coerced into JSON after retry."""

    def __init__(self, node: str, raw: str, cause: Exception):
        self.node = node
        self.raw = raw
        self.cause = cause
        super().__init__(f"[{node}] failed to parse JSON from model output: {cause}")


@dataclass
class LLMResult:
    node: str
    provider: str
    model: str
    prompt: str
    data: dict[str, Any]
    raw_text: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    cached: bool
    degraded: bool = False
    degraded_reason: str | None = None


def _cache_key(provider: str, model: str, temperature: float, prompt: str) -> str:
    h = hashlib.sha256()
    h.update(f"{provider}|{model}|{temperature}|{prompt}".encode("utf-8"))
    return h.hexdigest()


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _read_cache(key: str) -> dict[str, Any] | None:
    p = _cache_path(key)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _write_cache(key: str, payload: dict[str, Any]) -> None:
    _cache_path(key).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_json(text: str) -> dict[str, Any]:
    """Strip markdown fences and pull the outermost {...} object out of free text."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start : end + 1])
    raise json.JSONDecodeError("no JSON object found", cleaned, 0)


def _cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    in_rate, out_rate = RATE_TABLE.get(model, (0.0, 0.0))
    return (prompt_tokens / 1_000_000) * in_rate + (completion_tokens / 1_000_000) * out_rate


# ---------------------------------------------------------------------------
# Provider backends
# ---------------------------------------------------------------------------


def _call_gemini(model: str, prompt: str, temperature: float) -> tuple[str, int, int]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=temperature),
    )
    text = resp.text or ""
    usage = getattr(resp, "usage_metadata", None)
    prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
    completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
    return text, prompt_tokens, completion_tokens


def _call_openai_compatible(
    base_url: str, api_key_env: str, model: str, prompt: str, temperature: float
) -> tuple[str, int, int]:
    from openai import OpenAI

    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"{api_key_env} not set")
    client = OpenAI(base_url=base_url, api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    text = resp.choices[0].message.content or ""
    usage = resp.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    return text, prompt_tokens, completion_tokens


def _call_ollama_cloud(model: str, prompt: str, temperature: float) -> tuple[str, int, int]:
    return _call_openai_compatible("https://ollama.com/v1", "OLLAMA_API_KEY", model, prompt, temperature)


def _call_featherless(model: str, prompt: str, temperature: float) -> tuple[str, int, int]:
    return _call_openai_compatible(
        "https://api.featherless.ai/v1", "FEATHERLESS_API_KEY", model, prompt, temperature
    )


_BACKENDS = {
    "gemini": _call_gemini,
    "ollama": _call_ollama_cloud,
    "featherless": _call_featherless,
}


def _dispatch(provider: str, model: str, prompt: str, temperature: float) -> tuple[str, int, int]:
    fn = _BACKENDS[provider]
    return fn(model, prompt, temperature)


def call_llm(
    provider: str,
    model: str,
    prompt: str,
    *,
    temperature: float,
    node: str,
    max_retries: int = 3,
    fallback: tuple[str, str] | None = None,
) -> LLMResult:
    """
    Call an LLM, cached to disk by (provider, model, temperature, prompt).

    If `fallback` is given as (provider, model), a failure of the primary
    backend after retries falls back to it and the result is stamped
    `degraded=True` so callers/telemetry can report the substitution honestly.
    """
    key = _cache_key(provider, model, temperature, prompt)
    cached = _read_cache(key)
    if cached is not None:
        return LLMResult(node=node, cached=True, **cached)

    last_err: Exception | None = None
    for attempt in range(max_retries):
        start = time.monotonic()
        try:
            text, ptoks, ctoks = _dispatch(provider, model, prompt, temperature)
            latency_ms = (time.monotonic() - start) * 1000
            try:
                data = _extract_json(text)
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    time.sleep(min(2**attempt, 8))
                    continue
                raise NodeParseError(node, text, e) from e

            payload = dict(
                provider=provider,
                model=model,
                prompt=prompt,
                data=data,
                raw_text=text,
                latency_ms=latency_ms,
                prompt_tokens=ptoks,
                completion_tokens=ctoks,
                cost_usd=_cost(model, ptoks, ctoks),
                degraded=False,
                degraded_reason=None,
            )
            _write_cache(key, payload)
            return LLMResult(node=node, cached=False, **payload)
        except NodeParseError:
            raise
        except Exception as e:  # noqa: BLE001 - broad on purpose, provider SDKs vary
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(_retry_delay_seconds(e, attempt))
                continue

    if fallback is not None:
        fb_provider, fb_model = fallback
        result = call_llm(
            fb_provider,
            fb_model,
            prompt,
            temperature=temperature,
            node=node,
            max_retries=max_retries,
            fallback=None,
        )
        result.degraded = True
        result.degraded_reason = f"{provider}/{model} failed after {max_retries} attempts: {last_err}"
        return result

    raise RuntimeError(f"[{node}] {provider}/{model} failed after {max_retries} attempts: {last_err}")


@dataclass
class RawResult:
    """Like LLMResult but for free-text generation (no JSON coercion) — used by the baseline arm."""

    node: str
    provider: str
    model: str
    prompt: str
    text: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    cached: bool


def call_llm_raw(provider: str, model: str, prompt: str, *, temperature: float, node: str, max_retries: int = 3) -> RawResult:
    """Blocking free-text call, cached to disk like call_llm but without JSON parsing."""
    key = "raw:" + _cache_key(provider, model, temperature, prompt)
    cached = _read_cache(key)
    if cached is not None:
        return RawResult(node=node, cached=True, **cached)

    last_err: Exception | None = None
    for attempt in range(max_retries):
        start = time.monotonic()
        try:
            text, ptoks, ctoks = _dispatch(provider, model, prompt, temperature)
        except Exception as e:  # noqa: BLE001 - broad on purpose, provider SDKs vary
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(_retry_delay_seconds(e, attempt))
                continue
            raise RuntimeError(f"[{node}] {provider}/{model} failed after {max_retries} attempts: {last_err}") from e
        latency_ms = (time.monotonic() - start) * 1000
        payload = dict(
            provider=provider,
            model=model,
            prompt=prompt,
            text=text,
            latency_ms=latency_ms,
            prompt_tokens=ptoks,
            completion_tokens=ctoks,
            cost_usd=_cost(model, ptoks, ctoks),
        )
        _write_cache(key, payload)
        return RawResult(node=node, cached=False, **payload)


def stream_gemini_raw(model: str, prompt: str, temperature: float):
    """Yield text chunks from Gemini as they arrive. Not cached — used for the live UI race."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=temperature),
    ):
        if chunk.text:
            yield chunk.text


def stream_ollama_raw(model: str, prompt: str, temperature: float):
    """Yield text chunks from an Ollama Cloud model as they arrive. Not cached — used for the live UI race."""
    from openai import OpenAI

    client = OpenAI(base_url="https://ollama.com/v1", api_key=os.environ["OLLAMA_API_KEY"])
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
