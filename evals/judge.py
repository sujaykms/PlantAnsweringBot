"""DeepEval judge backed by app.llm.chat (OpenRouter). Must be a different family than ANSWER_MODEL."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

from deepeval.models import DeepEvalBaseLLM  # noqa: E402

from app import llm  # noqa: E402
from app.config import get_settings  # noqa: E402

DEFAULT_JUDGE = "openai/gpt-4.1-mini"


def judge_model_name() -> str:
    if os.environ.get("JUDGE_MODEL"):
        return os.environ["JUDGE_MODEL"]
    try:  # settings ignore unknown keys, so read backend/.env directly
        for line in (Path(__file__).resolve().parents[1] / "backend" / ".env").read_text().splitlines():
            if line.startswith("JUDGE_MODEL="):
                return line.split("=", 1)[1].strip() or DEFAULT_JUDGE
    except OSError:
        pass
    return DEFAULT_JUDGE


def check_family(judge: str, answer: str | None = None) -> None:
    answer = answer or get_settings().answer_model
    if judge.split("/")[0] == answer.split("/")[0]:
        raise SystemExit(f"JUDGE_MODEL ({judge}) must be a different family than ANSWER_MODEL ({answer})")


class OpenRouterJudge(DeepEvalBaseLLM):
    def __init__(self, model: str | None = None):
        self.model_name = model or judge_model_name()
        super().__init__(self.model_name)

    def load_model(self, *args, **kwargs):
        return self

    def get_model_name(self, *args, **kwargs) -> str:
        return self.model_name

    def generate(self, prompt: str, schema=None, **kwargs):
        text = llm.chat(self.model_name, [{"role": "user", "content": prompt}], max_tokens=4000)
        if schema is not None:
            return schema(**llm.parse_json(text))
        return text

    async def a_generate(self, prompt: str, schema=None, **kwargs):
        return await asyncio.to_thread(self.generate, prompt, schema)
