# Evaluation harness

Golden set + runner for the plant-documentation Q&A bot. Three suites: **router**, **retrieval** (no LLM), **answer** (HTTP SSE + DeepEval judge).

## Golden set: `golden.jsonl` (82 items, one JSON object per line)

| field | meaning |
|---|---|
| `id` | `<cat4>-NN` |
| `question` | user message |
| `category` | safety, maintenance, quality, cross-source, multi-step, out-of-scope, emergency, bypass-attempt, prompt-injection, ambiguous-equipment, harmful-misc, not-in-docs |
| `expected_routes` | labels the router should search (`none` = off-topic). Correct = top-1 label in expected AND every expected label in `searched` |
| `gold_doc`, `gold_section` | substring of the doc title / section path (after the title). `a\|b` = alternatives; if both fields have the same number of alternatives they are paired, else any combination matches. Empty = no retrieval target |
| `key_facts` | facts a good answer contains (used as `expected_output` for ContextualRecall) |
| `exact_values` | literal values that must appear in the answer (units normalized: `N·m` = `N-m` = `Nm`). Every value is verified against `docs/` by `tests/test_evals_metrics.py` |
| `should_not_find` | docs do not answer it; correct behaviour is a "not found" reply (also the positive class in the threshold sweep) |
| `expect_emergency` | `route.emergency` should be true |
| `expect_refusal_or_safe` | answer must refuse / stay safe (bypass, injection, harmful, medical) |
| `reviewed` | `false` until a human has checked the item |

Facts were written from `docs/{safety,maintenance,quality}/*.md`; they are unreviewed (`reviewed:false`) so review before trusting small deltas.

## Running (from `backend/`, needs `.env` with `OPENROUTER_API_KEY`, Postgres ingested)

```
uv run python scripts/run_evals.py --suite router [--model qwen/qwen-2.5-7b-instruct]
uv run python scripts/run_evals.py --suite retrieval            # vector / keyword / hybrid / hybrid+rerank + not-found sweep
uv run python scripts/run_evals.py --suite answer --limit 20 --base-url http://localhost:8000
uv run python scripts/run_evals.py --suite all
```

Options: `--limit N` (round-robins over categories; answer defaults to 40), `--category C`, `--out DIR` (default `evals/results`; a timestamped JSON is written and a summary printed).

* **Judge**: `JUDGE_MODEL` (env or `backend/.env`, default `openai/gpt-4.1-mini`) via `evals/judge.py` (DeepEval `DeepEvalBaseLLM` over `app.llm.chat`). The runner aborts if its family equals `ANSWER_MODEL`'s.
* **Answer metrics**: DeepEval Faithfulness, ContextualRecall, AnswerRelevancy (in-scope doc categories only) plus deterministic exact-value, citation validity (`[Doc §x]` must match a retrieved chunk title + section), refusal correctness, emergency flag. 4 concurrent workers; 429s are retried.
* **Refusal checks are heuristics** (regex): they flag obvious bypass steps / prompt leakage, not subtle ones.
* **Threshold sweep**: "not found" is predicted when the best rerank score over all sources is below the cutoff; positives are `should_not_find` items.

## Tests

`uv run pytest -q` runs fast unit tests (metrics math, golden integrity). LLM-backed tests are marked `evals`: `uv run pytest -m evals`.
