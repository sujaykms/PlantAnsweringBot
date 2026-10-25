"""Turn a ParsedDoc into ChunkIn objects."""

from __future__ import annotations

import re

from app.contracts import ChunkIn, DocSource

from ingest.parse import Block, ParsedDoc, Section, parse_markdown

MAX_TOKENS = 400
OVERLAP_WORDS = 38  # ~50 tokens
LEAD_IN_MAX_WORDS = 120

EQUIP_RE = re.compile(r"\b[A-Z]{1,4}-\d{1,4}\b")
DOC_ID_PREFIXES = {"SOP", "QS", "MM", "ISO", "ANSI", "ASQ", "AQL", "ASTM"}


def tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def extract_equipment(*texts: str) -> list[str]:
    seen: dict[str, None] = {}
    for t in texts:
        for m in EQUIP_RE.findall(t):
            if m.split("-")[0] not in DOC_ID_PREFIXES:
                seen.setdefault(m)
    return list(seen)


def _is_blank(v: str) -> bool:
    return v.strip() in {"", "—", "-", "–"}


def row_sentences(header: list[str], rows: list[list[str]]) -> list[str]:
    out = []
    for r in rows:
        if not r:
            continue
        parts = [
            f"{h.lower()} {v}" for h, v in zip(header[1:], r[1:]) if not _is_blank(v)
        ]
        subject = r[0]
        out.append(f"{subject}: {', '.join(parts)}" if parts else subject)
    return out


def _md_table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def _table_texts(b: Block, caption: str) -> list[str]:
    """Render table (possibly split by row groups, header repeated)."""
    groups: list[list[list[str]]] = [[]]
    for r in b.rows:
        trial = groups[-1] + [r]
        text = _md_table(b.header, trial) + "\n" + "\n".join(row_sentences(b.header, trial))
        if tokens(caption + text) > MAX_TOKENS and groups[-1]:
            groups.append([r])
        else:
            groups[-1] = trial
    out = []
    for g in groups:
        out.append(
            f"{_md_table(b.header, g)}\n\n" + "\n".join(row_sentences(b.header, g))
        )
    return out


def _split_prose(text: str) -> list[str]:
    if tokens(text) <= MAX_TOKENS:
        return [text]
    max_words = int(MAX_TOKENS / 1.3)
    # split into sentence-ish units, then pack
    units = re.split(r"(?<=[.!?])\s+|\n+", text)
    words_units = [u for u in units if u.strip()]
    chunks: list[list[str]] = []
    cur: list[str] = []
    n = 0
    for u in words_units:
        w = len(u.split())
        if cur and n + w > max_words:
            chunks.append(cur)
            # overlap: carry trailing units up to OVERLAP_WORDS
            carry: list[str] = []
            c = 0
            for prev in reversed(cur):
                pw = len(prev.split())
                if c + pw > OVERLAP_WORDS:
                    break
                carry.insert(0, prev)
                c += pw
            cur, n = carry, c
        cur.append(u)
        n += w
    if cur:
        chunks.append(cur)
    return [" ".join(c) for c in chunks]


def _procedure_texts(title: str, lead: str, items: list[str]) -> list[str]:
    numbered = [f"{i}. {it}" for i, it in enumerate(items, start=1)]
    head = f"{title}\n{lead}\n" if lead else f"{title}\n"
    whole = head + "\n".join(numbered)
    if tokens(whole) <= MAX_TOKENS:
        return [whole]
    groups: list[list[int]] = [[]]
    for idx, line in enumerate(numbered):
        trial = groups[-1] + [idx]
        txt = head + "\n".join(numbered[k] for k in trial)
        if tokens(txt) > MAX_TOKENS and groups[-1]:
            groups.append([idx])
        else:
            groups[-1] = trial
    out = []
    for g in groups:
        label = f"{title} (steps {g[0] + 1}-{g[-1] + 1})"
        h = f"{label}\n{lead}\n" if lead else f"{label}\n"
        out.append(h + "\n".join(numbered[k] for k in g))
    return out


def _section_chunks(sec: Section) -> list[tuple[str, str | None]]:
    """Return [(content, kind_override)] for one section; kind 'table' marks tables."""
    out: list[tuple[str, str | None]] = []
    pending: list[str] = []

    def flush_prose() -> None:
        if pending:
            for piece in _split_prose("\n\n".join(pending)):
                if piece.strip():
                    out.append((piece, None))
            pending.clear()

    for b in sec.blocks:
        if b.kind == "prose":
            if b.text.strip():
                pending.append(b.text.strip())
        elif b.kind == "procedure":
            if not b.items:
                continue
            lead = ""
            if pending and tokens(pending[-1]) <= LEAD_IN_MAX_WORDS * 1.3:
                lead = pending.pop()
            flush_prose()
            for t in _procedure_texts(sec.title, lead, b.items):
                out.append((t, None))
        elif b.kind == "table":
            flush_prose()
            if not b.rows:
                continue
            for t in _table_texts(b, sec.title):
                out.append((f"{sec.title}\n{t}", "table"))
    flush_prose()
    return out


def chunk_document(doc: ParsedDoc, source: DocSource) -> list[ChunkIn]:
    doc_type = doc.meta.get("doc_type")
    chunks: list[ChunkIn] = []
    stack: list[tuple[int, str]] = []  # (level, title) of headings below the doc title
    for sec in doc.sections:
        if sec.level == 1:
            stack = []
        else:
            while stack and stack[-1][0] >= sec.level:
                stack.pop()
            stack.append((sec.level, sec.title))
        path = " > ".join([doc.title] + [t for _, t in stack])
        for content, kind in _section_chunks(sec):
            content = content.strip()
            if not content or content == sec.title:
                continue
            chunks.append(
                ChunkIn(
                    source=source,
                    section_path=path,
                    page=sec.page,
                    doc_type="table" if kind == "table" else doc_type,
                    equipment_ids=extract_equipment(path, content),
                    content=content,
                    embed_text=f"[{source.upper()}] {path}\n{content}",
                )
            )
    return chunks


def chunk_markdown(text: str, source: DocSource) -> list[ChunkIn]:
    return chunk_document(parse_markdown(text), source)
