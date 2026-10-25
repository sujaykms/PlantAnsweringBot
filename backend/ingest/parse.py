"""Parse Markdown / PDF into a flat list of sections with typed blocks."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt


@dataclass
class Block:
    kind: str  # "prose" | "procedure" | "table"
    text: str = ""                      # prose text
    items: list[str] = field(default_factory=list)   # procedure steps
    header: list[str] = field(default_factory=list)  # table header
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class Section:
    level: int            # 1 = document title, 2.. = sub headings
    title: str
    blocks: list[Block] = field(default_factory=list)
    page: int | None = None


@dataclass
class ParsedDoc:
    meta: dict[str, str]
    title: str
    sections: list[Section]


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip("'\"")
    return meta, text[m.end():]


def _clean_cell(s: str) -> str:
    return re.sub(r"[*`]", "", s).strip()


def parse_markdown(text: str) -> ParsedDoc:
    meta, body = split_front_matter(text)
    lines = body.splitlines()
    tokens = MarkdownIt("commonmark").enable("table").parse(body)
    sections: list[Section] = []
    cur = Section(level=1, title=meta.get("title", ""))
    sections.append(cur)

    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.level != 0:
            i += 1
            continue
        if t.nesting == 0:  # fence, hr, html block
            if t.map and t.type != "hr":
                txt = "\n".join(lines[t.map[0]:t.map[1]]).strip()
                if txt:
                    cur.blocks.append(Block("prose", text=txt))
            i += 1
            continue
        j = i + 1
        while not (tokens[j].level == 0 and tokens[j].nesting == -1):
            j += 1
        if t.type == "heading_open":
            title = tokens[i + 1].content.strip()
            lvl = int(t.tag[1])
            if lvl == 1 and not meta.get("title"):
                meta["title"] = title
            cur = Section(level=lvl, title=title)
            sections.append(cur)
        elif t.type == "table_open":
            header, rows, row = [], [], []
            in_head = False
            for k in range(i, j):
                tk = tokens[k]
                if tk.type == "thead_open":
                    in_head = True
                elif tk.type == "thead_close":
                    in_head = False
                elif tk.type == "tr_open":
                    row = []
                elif tk.type == "inline":
                    row.append(_clean_cell(tk.content))
                elif tk.type == "tr_close":
                    (header.extend(row) if in_head else rows.append(row))
            cur.blocks.append(Block("table", header=header, rows=rows))
        elif t.type == "ordered_list_open":
            items = []
            for k in range(i, j):
                tk = tokens[k]
                if tk.type == "list_item_open" and tk.level == 1 and tk.map:
                    raw = lines[tk.map[0]:tk.map[1]]
                    first = re.sub(r"^\s*\d+[.)]\s+", "", raw[0])
                    items.append("\n".join([first] + [r.strip() for r in raw[1:]]).strip())
            cur.blocks.append(Block("procedure", items=items))
        elif t.map:
            txt = "\n".join(lines[t.map[0]:t.map[1]]).strip()
            if txt:
                cur.blocks.append(Block("prose", text=txt))
        i = j + 1

    return ParsedDoc(meta=meta, title=meta.get("title", ""), sections=sections)


# ---------------------------------------------------------------- PDF

_NUM_HEADING = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+\S")
_STEP = re.compile(r"^\d+[.)]\s+")


def parse_pdf(path: Path) -> ParsedDoc:
    import pymupdf

    doc = pymupdf.open(path)
    # (page, text, size, bold)
    lines: list[tuple[int, str, float, bool]] = []
    for pno, page in enumerate(doc, start=1):
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                spans = [s for s in ln["spans"] if s["text"].strip()]
                if not spans:
                    continue
                txt = " ".join(s["text"].strip() for s in spans)
                size = max(s["size"] for s in spans)
                bold = all(s["flags"] & 16 for s in spans)
                lines.append((pno, txt, round(size, 1), bold))
    if not lines:
        return ParsedDoc({}, path.stem, [])
    body = Counter()
    for _, t, s, _ in lines:
        body[s] += len(t)
    body_size = body.most_common(1)[0][0]
    big = sorted({s for _, _, s, _ in lines if s > body_size * 1.12}, reverse=True)

    def heading_level(t: str, size: float, bold: bool) -> int | None:
        if size in big:
            return 1 + big.index(size)
        if _STEP.match(t) and "." not in t.split()[0].rstrip(".)"):
            m = None  # "1. Do x" is a step, not a heading
        else:
            m = _NUM_HEADING.match(t)
        if m and len(t) < 80 and bold:
            return 2 + m.group(1).count(".")
        return None

    title = ""
    sections: list[Section] = []
    cur: Section | None = None
    para: list[str] = []
    steps: list[str] = []

    def flush() -> None:
        nonlocal para, steps
        if cur is None:
            para, steps = [], []
            return
        if para:
            cur.blocks.append(Block("prose", text=" ".join(para)))
        if steps:
            cur.blocks.append(Block("procedure", items=steps))
        para, steps = [], []

    for pno, t, size, bold in lines:
        lvl = heading_level(t, size, bold)
        if lvl is not None:
            flush()
            if lvl == 1 and not title:
                title = t
            cur = Section(level=lvl or 2, title=t, page=pno)
            sections.append(cur)
            continue
        if cur is None:
            cur = Section(level=1, title=title or path.stem, page=pno)
            sections.append(cur)
        if _STEP.match(t):
            if para:
                cur.blocks.append(Block("prose", text=" ".join(para)))
                para = []
            steps.append(_STEP.sub("", t))
        elif steps:  # continuation of previous step
            steps[-1] += " " + t
        else:
            para.append(t)
    flush()
    title = title or path.stem
    for s in sections:
        if s.level == 1:
            break
    else:
        sections.insert(0, Section(level=1, title=title, page=1))
    return ParsedDoc(meta={"title": title}, title=title, sections=sections)


def parse_file(path: Path) -> ParsedDoc:
    if path.suffix.lower() == ".pdf":
        return parse_pdf(path)
    return parse_markdown(path.read_text(encoding="utf-8"))
