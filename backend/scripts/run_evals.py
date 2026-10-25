"""Evaluation harness. Run from backend/:

    uv run python scripts/run_evals.py --suite {router,retrieval,answer,all} [--model M] [--limit N]
        [--base-url http://localhost:8000] [--out ../evals/results] [--category C]
"""

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))
os.chdir(BACKEND)  # pydantic-settings reads ./.env

from evals import metrics as M  # noqa: E402
from evals.metrics import load_golden  # noqa: E402

DOC_CATS = {"safety", "maintenance", "quality", "cross-source", "multi-step", "ambiguous-equipment"}
SAFETY_CATS = {"bypass-attempt", "prompt-injection", "harmful-misc"}


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(x, pct=True):
    if x is None:
        return "  n/a"
    return f"{x:5.0%}" if pct else f"{x:6.3f}"


def table(headers, rows):
    w = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h)) for i, h in enumerate(headers)]
    line = lambda r: "| " + " | ".join(str(c).ljust(w[i]) for i, c in enumerate(r)) + " |"
    out = [line(headers), "|" + "|".join("-" * (x + 2) for x in w) + "|"] + [line(r) for r in rows]
    print("\n".join(out))


def select(items, limit, category):
    if category:
        items = [i for i in items if i["category"] == category]
    if not limit or limit >= len(items):
        return items
    by = defaultdict(list)  # round-robin over categories so every category is represented
    for i in items:
        by[i["category"]].append(i)
    out, queues = [], list(by.values())
    while len(out) < limit and any(queues):
        for q in queues:
            if q and len(out) < limit:
                out.append(q.pop(0))
    return out


def percentile(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


# ============================== router ==============================
def run_router(items, model):
    from app.routing.router import route

    rows = []
    for it in items:
        d = route(it["question"], model=model)
        got = list(d.searched) or ["none"]
        exp = it["expected_routes"]
        top_ok = got[0] in exp
        covered = set(exp) <= set(got)
        # fallback to all sources is "unrouted"; count correct only if exp is the full set
        rows.append({
            "id": it["id"], "category": it["category"], "expected": exp, "got": got,
            "correct": top_ok and covered, "top_ok": top_ok, "coverage": len(set(exp) & set(got)) / len(set(exp)),
            "fallback": d.fallback, "emergency_pred": bool(getattr(d, "emergency", False)),
            "expect_emergency": it["expect_emergency"], "latency_ms": d.latency_ms,
        })
    emer = [r for r in rows if r["expect_emergency"]]
    lat = [r["latency_ms"] for r in rows]
    summary = {
        "model": model or "(default ROUTER_MODEL)", "n": len(rows),
        "accuracy": mean([r["correct"] for r in rows]),
        "top1_in_expected": mean([r["top_ok"] for r in rows]),
        "label_set_coverage": mean([r["coverage"] for r in rows]),
        "fallback_rate": mean([r["fallback"] for r in rows]),
        "emergency_recall": mean([r["emergency_pred"] for r in emer]) if emer else None,
        "emergency_n": len(emer),
        "emergency_supported": any(hasattr(r, "emergency") for r in [d]),
        "latency_p50_ms": percentile(lat, 0.5), "latency_p95_ms": percentile(lat, 0.95),
    }
    cats = {}
    for c in sorted({r["category"] for r in rows}):
        rs = [r for r in rows if r["category"] == c]
        cats[c] = {"n": len(rs), "accuracy": mean([r["correct"] for r in rs]),
                   "coverage": mean([r["coverage"] for r in rs])}
    print(f"\n## Router  (model={summary['model']}, n={summary['n']})\n")
    table(["metric", "value"], [
        ["label accuracy (top1 in expected AND expected ⊆ searched)", fmt(summary["accuracy"])],
        ["top-1 in expected", fmt(summary["top1_in_expected"])],
        ["label-set coverage", fmt(summary["label_set_coverage"])],
        ["fallback-to-all rate", fmt(summary["fallback_rate"])],
        [f"emergency recall (n={summary['emergency_n']}; RouteDecision.emergency "
         f"{'present' if summary['emergency_supported'] else 'absent'})", fmt(summary["emergency_recall"])],
        ["latency p50 / p95 (ms)", f"{summary['latency_p50_ms']} / {summary['latency_p95_ms']}"],
    ])
    print()
    table(["category", "n", "accuracy", "coverage"], [[c, v["n"], fmt(v["accuracy"]), fmt(v["coverage"])] for c, v in cats.items()])
    bad = [r for r in rows if not r["correct"]]
    if bad:
        print("\nMisroutes:")
        for r in bad[:15]:
            print(f"  {r['id']:8} exp={'+'.join(r['expected']):28} got={'+'.join(r['got'])}")
    return {"summary": summary, "by_category": cats, "items": rows}


# ============================== retrieval ==============================
def _fetch(sql, params):
    from app import db

    with db.get_pool().connection() as conn:
        return conn.execute(sql, params).fetchall()


def _vector_only(q_emb, sources, k):
    rows = _fetch(
        "select d.title, c.section_path from chunks c join documents d on d.id=c.document_id "
        "where c.source = any(%s) order by c.embedding <=> %s::vector limit %s", (sources, q_emb, k))
    return [(r["title"], r["section_path"]) for r in rows]


def _keyword_only(question, sources, k):
    rows = _fetch(
        "select d.title, c.section_path from chunks c join documents d on d.id=c.document_id, "
        "websearch_to_tsquery('english', %s) q where c.source = any(%s) and c.tsv @@ q "
        "order by ts_rank_cd(c.tsv, q) desc limit %s", (question, sources, k))
    return [(r["title"], r["section_path"]) for r in rows]


def run_retrieval(items):
    from app import embeddings, retrieval
    from app.config import get_settings
    from app.contracts import DOC_SOURCES

    s = get_settings()
    k = s.top_k
    sources = list(DOC_SOURCES)
    embeddings.warm_up()
    variants = ["vector", "keyword", "hybrid", "hybrid+rerank"]
    per_item, best_scores = [], {}
    for it in items:
        q = it["question"]
        q_emb = embeddings.embed_query(q)
        res = {
            "vector": _vector_only(q_emb, sources, k),
            "keyword": _keyword_only(q, sources, k),
            "hybrid": [(c.title, c.section_path) for c in retrieval.hybrid_search(q, sources, k)],
        }
        rr = retrieval.retrieve(q, sources)
        res["hybrid+rerank"] = [(c.title, c.section_path) for c in rr]
        best_scores[it["id"]] = max((c.rerank_score for c in rr if c.rerank_score is not None), default=None)
        if it["gold_doc"]:
            ranks = {v: M.first_hit_rank(res[v], it["gold_doc"], it["gold_section"]) for v in variants}
            doc_ranks = {v: M.first_hit_rank(res[v], it["gold_doc"]) for v in variants}
            per_item.append({"id": it["id"], "category": it["category"], "ranks": ranks, "doc_ranks": doc_ranks,
                             "top": {v: [f"{t.split()[0]} > {sp.split(' > ', 1)[-1]}" for t, sp in res[v][:3]] for v in variants},
                             "best_rerank": best_scores[it["id"]]})
    out = {"k": k, "n_gold": len(per_item), "variants": {}, "by_category": {}}
    for v in variants:
        rk = [p["ranks"][v] for p in per_item]
        dk = [p["doc_ranks"][v] for p in per_item]
        out["variants"][v] = {"recall@k": M.recall_at_k(rk, k), "mrr": M.mrr(rk),
                              "doc_recall@k": M.recall_at_k(dk, k), "doc_mrr": M.mrr(dk)}
    cats = sorted({p["category"] for p in per_item})
    for c in cats:
        ps = [p for p in per_item if p["category"] == c]
        out["by_category"][c] = {"n": len(ps), **{
            v: M.recall_at_k([p["ranks"][v] for p in ps], k) for v in variants}}
    print(f"\n## Retrieval  (gold items n={len(per_item)}, k={k}, all 3 sources searched, no LLM calls)\n")
    table(["variant", f"recall@{k} (doc+section)", "MRR", f"doc recall@{k}", "doc MRR"],
          [[v, fmt(d["recall@k"]), fmt(d["mrr"], False), fmt(d["doc_recall@k"]), fmt(d["doc_mrr"], False)]
           for v, d in out["variants"].items()])
    print()
    table(["category", "n"] + [f"R@{k} {v}" for v in variants],
          [[c, d["n"]] + [fmt(d[v]) for v in variants] for c, d in out["by_category"].items()])
    miss = [p for p in per_item if p["ranks"]["hybrid+rerank"] is None]
    if miss:
        print("\nMissed by hybrid+rerank (gold not in top-k):")
        for p in miss:
            print(f"  {p['id']:8} top3={p['top']['hybrid+rerank']}")

    # ---- not-found threshold sweep ----
    ids = [it["id"] for it in items]
    scores = [best_scores[i] for i in ids]
    nf = [it["should_not_find"] for it in items]
    cutoffs = [float(c) for c in range(-12, 1)]
    sweep = M.threshold_sweep(scores, nf, cutoffs)
    best = M.best_cutoff(sweep)
    cur = M.threshold_sweep(scores, nf, [s.min_rerank_score])[0]
    out["not_found_sweep"] = {"rows": sweep, "best": best, "current": cur, "n_not_found": sum(nf), "n_in_scope": len(nf) - sum(nf)}
    print(f"\n### Not-found threshold sweep (positives = should_not_find, n={sum(nf)}; in-scope n={len(nf) - sum(nf)}; "
          f"'not found' when best rerank score < cutoff, all sources)\n")
    table(["cutoff", "precision", "recall", "F1", "tp", "fp", "fn"],
          [[f"{r['cutoff']:.1f}", fmt(r["precision"]), fmt(r["recall"]), fmt(r["f1"]), r["tp"], r["fp"], r["fn"]] for r in sweep])
    print(f"\ncurrent cutoff {s.min_rerank_score}: P={fmt(cur['precision']).strip()} R={fmt(cur['recall']).strip()} F1={fmt(cur['f1']).strip()}")
    print(f"recommended cutoff (max F1): {best['cutoff']:.1f}  P={fmt(best['precision']).strip()} R={fmt(best['recall']).strip()} F1={fmt(best['f1']).strip()}")
    out["items"] = per_item
    return out


# ============================== answer ==============================
def call_chat(base_url, question, timeout=180):
    import httpx

    t0 = time.perf_counter()
    lines = []
    for attempt in range(6):  # back off on rate limiting (429) from the backend
        lines = []
        with httpx.stream("POST", f"{base_url}/chat", json={"message": question}, timeout=timeout) as r:
            if r.status_code == 429 and attempt < 5:
                time.sleep(min(30, float(r.headers.get("retry-after", 2 ** (attempt + 1)))))
                continue
            r.raise_for_status()
            for line in r.iter_lines():
                lines.append(line)
        break
    route, chunks, tokens, done, err, statuses = {}, [], [], {}, None, []
    for ev, data in M.parse_sse(lines):
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            payload = {}
        if ev == "route":
            route = payload
        elif ev == "sources":
            chunks = payload.get("chunks", [])
        elif ev == "token":
            tokens.append(payload.get("text", ""))
        elif ev == "done":
            done = payload
        elif ev == "error":
            err = payload.get("message", "error")
        elif ev == "status":
            statuses.append(payload)
        # unknown events are ignored
    return {"route": route, "chunks": chunks, "answer": "".join(tokens), "done": done, "error": err,
            "latency_s": time.perf_counter() - t0}


def deterministic(it, r):
    a, cat = r["answer"], it["category"]
    out = {}
    out["exact_values"] = M.exact_values_score(it["exact_values"], a)
    cs = M.citation_score(a, r["chunks"])
    out["citations_n"], out["citations_valid"] = cs["n"], cs["valid"]
    out["citation_validity"] = cs["valid"] / cs["n"] if cs["n"] else None
    nf = M.says_not_found(a, bool(r["done"].get("not_found")))
    out["refusal_correct"] = None
    if it["should_not_find"]:
        out["refusal_correct"] = nf
    if cat in SAFETY_CATS:
        ro = M.refusal_ok(a)
        out["safety_ok"] = ro["ok"]
        out["gives_steps"] = ro["gives_steps"]
        out["prompt_leak"] = ro["prompt_leak"]
        if not it["should_not_find"]:
            out["refusal_correct"] = ro["ok"]
        else:
            out["refusal_correct"] = nf or ro["ok"]
    out["emergency_flag"] = (bool(r["route"].get("emergency")) if it["expect_emergency"] else None)
    return out


def llm_metrics(it, r, judge):
    from deepeval.metrics import AnswerRelevancyMetric, ContextualRecallMetric, FaithfulnessMetric
    from deepeval.test_case import LLMTestCase

    ctx = [c["content"] for c in r["chunks"]]
    if not ctx or not r["answer"]:
        return {}
    tc = LLMTestCase(input=it["question"], actual_output=r["answer"],
                     expected_output="; ".join(it["key_facts"]) or r["answer"], retrieval_context=ctx)
    out = {}
    for name, cls in [("faithfulness", FaithfulnessMetric), ("contextual_recall", ContextualRecallMetric),
                      ("answer_relevancy", AnswerRelevancyMetric)]:
        try:
            m = cls(model=judge, async_mode=False, include_reason=False)
            m.measure(tc)
            out[name] = float(m.score)
        except Exception as e:  # keep the run alive; record failure
            out[name] = None
            out[f"{name}_error"] = str(e)[:120]
    return out


def run_answer(items, base_url, workers=4):
    import httpx
    from evals.judge import OpenRouterJudge, check_family, judge_model_name

    try:
        httpx.get(f"{base_url}/health", timeout=5).raise_for_status()
    except Exception as e:
        print(f"\n## Answer suite SKIPPED: {base_url}/health unreachable ({e})")
        return {"skipped": f"{base_url} unreachable"}
    check_family(judge_model_name())
    judge = OpenRouterJudge()

    def work(it):
        try:
            r = call_chat(base_url, it["question"])
        except Exception as e:
            return {"id": it["id"], "category": it["category"], "error": str(e)[:200]}
        res = {"id": it["id"], "category": it["category"], "answer": r["answer"], "error": r["error"],
               "route": r["route"].get("searched"), "n_chunks": len(r["chunks"]), "latency_s": round(r["latency_s"], 2),
               "not_found": bool(r["done"].get("not_found")), **deterministic(it, r)}
        if it["category"] in DOC_CATS and not it["should_not_find"]:
            res.update(llm_metrics(it, r, judge))
        return res

    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(work, items))
    keys = ["faithfulness", "contextual_recall", "answer_relevancy", "exact_values", "citation_validity",
            "refusal_correct", "emergency_flag"]
    ok = [r for r in rows if "error" not in r or r.get("answer")]
    summary = {k: mean([r.get(k) for r in ok]) for k in keys}
    summary["n"], summary["errors"] = len(rows), sum(1 for r in rows if r.get("error"))
    summary["judge"] = judge.get_model_name()
    cats = {}
    for c in sorted({r["category"] for r in rows}):
        rs = [r for r in ok if r["category"] == c]
        cats[c] = {"n": len(rs), **{k: mean([r.get(k) for r in rs]) for k in keys}}
    print(f"\n## Answer  (backend={base_url}, judge={summary['judge']}, n={summary['n']}, errors={summary['errors']})\n")
    table(["metric", "mean"], [[k, fmt(summary[k])] for k in keys])
    print()
    short = {"faithfulness": "faith", "contextual_recall": "ctxRec", "answer_relevancy": "relev", "exact_values": "exact",
             "citation_validity": "cite", "refusal_correct": "refuse", "emergency_flag": "emerg"}
    table(["category", "n"] + [short[k] for k in keys], [[c, v["n"]] + [fmt(v[k]) for k in keys] for c, v in cats.items()])
    return {"summary": summary, "by_category": cats, "items": rows}


# ============================== main ==============================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=["router", "retrieval", "answer", "all"], required=True)
    ap.add_argument("--model", default=None, help="router model override")
    ap.add_argument("--limit", type=int, default=None, help="max items (answer suite defaults to 40)")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--out", default=str(ROOT / "evals" / "results"))
    ap.add_argument("--category", default=None)
    args = ap.parse_args()

    golden = load_golden()
    result = {"timestamp": datetime.now().isoformat(timespec="seconds"), "golden_size": len(golden)}
    if args.suite in ("router", "all"):
        result["router"] = run_router(select(golden, args.limit, args.category), args.model)
    if args.suite in ("retrieval", "all"):
        result["retrieval"] = run_retrieval(select(golden, args.limit, args.category))
    if args.suite in ("answer", "all"):
        result["answer"] = run_answer(select(golden, args.limit or 40, args.category), args.base_url)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
