"""Single OpenRouter client (OpenAI-compatible API)."""

import json
from collections.abc import Iterator
from functools import lru_cache

from openai import OpenAI

from app.config import get_settings


@lru_cache
def get_client() -> OpenAI:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set (backend/.env)")
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        default_headers={"X-Title": "Plant Docs Q&A"},
    )


def chat(
    model: str,
    messages: list[dict],
    json_schema: dict | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> str:
    """Non-streaming completion. With json_schema, requests structured output."""
    kwargs: dict = {}
    if json_schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "output", "strict": True, "schema": json_schema},
        }
    resp = get_client().chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    return resp.choices[0].message.content or ""


def chat_stream(model: str, messages: list[dict], temperature: float = 0.2) -> Iterator[str]:
    stream = get_client().chat.completions.create(
        model=model, messages=messages, temperature=temperature, stream=True
    )
    for event in stream:
        if event.choices and (delta := event.choices[0].delta.content):
            yield delta


def parse_json(text: str) -> dict:
    """Tolerant JSON parse for small models that wrap output in prose or fences."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in model output: {text[:200]!r}")
    return json.loads(text[start : end + 1])
