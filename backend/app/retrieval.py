import re

from app import db, embeddings
from app.config import get_settings
from app.contracts import DOC_SOURCES, RetrievedChunk, RouteDecision, RouteLabel

# e.g. P-101, BRK-200, CNV-3
EQUIP_RE = re.compile(r"\b[A-Za-z]{1,5}-\d{1,5}[A-Za-z]?\b")

_SQL = "select * from hybrid_search(%s::vector, %s, %s, %s, %s, %s)"


def extract_equipment(question: str) -> list[str]:
    return sorted({m.upper() for m in EQUIP_RE.findall(question)})


def hybrid_search(question: str, sources: list[str], k: int) -> list[RetrievedChunk]:
    q_emb = embeddings.embed_query(question)
    equip = extract_equipment(question)
    with db.get_pool().connection() as conn:
        rows = conn.execute(_SQL, (q_emb, question, list(sources), k, equip, k)).fetchall()
    return [RetrievedChunk(**r) for r in rows]


def select_top(
    chunks: list[RetrievedChunk], sources: list[str], top_k: int
) -> list[RetrievedChunk]:
    """Top-k by rerank score, guaranteeing >=2 per searched source when several are searched."""

    def key(c: RetrievedChunk) -> float:
        return c.rerank_score if c.rerank_score is not None else float("-inf")

    ranked = sorted(chunks, key=key, reverse=True)
    chosen: list[RetrievedChunk] = []
    if len(set(sources)) > 1:
        for s in dict.fromkeys(sources):
            chosen += [c for c in ranked if c.source == s][:2]
    ids = {c.id for c in chosen}
    for c in ranked:
        if len(chosen) >= top_k:
            break
        if c.id not in ids:
            chosen.append(c)
            ids.add(c.id)
    return sorted(chosen, key=key, reverse=True)


def retrieve(question: str, sources: list[RouteLabel]) -> list[RetrievedChunk]:
    """Hybrid search THEN cross-encoder rerank (always)."""
    s = get_settings()
    if not sources:
        return []
    cands = hybrid_search(question, list(sources), s.rerank_candidates)
    if not cands:
        return []
    scores = embeddings.rerank(question, [c.content for c in cands])
    for c, sc in zip(cands, scores):
        c.rerank_score = float(sc)
    return select_top(cands, list(sources), s.top_k)


def _weak(chunks: list[RetrievedChunk]) -> bool:
    best = max((c.rerank_score for c in chunks if c.rerank_score is not None), default=None)
    return best is None or best < get_settings().min_rerank_score


def retrieve_with_fallback(
    question: str, decision: RouteDecision
) -> tuple[list[RetrievedChunk], bool]:
    chunks = retrieve(question, decision.searched)
    weak = _weak(chunks)
    if weak and set(decision.searched) != set(DOC_SOURCES):
        decision.fallback = True
        decision.searched = list(DOC_SOURCES)
        chunks = retrieve(question, decision.searched)
        weak = _weak(chunks)
    return chunks, weak
