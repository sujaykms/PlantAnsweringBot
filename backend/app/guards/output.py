"""Deterministic OUTPUT guardrails (no LLM). verify() -> Verification."""

import re

from app.contracts import RetrievedChunk, RouteDecision, Verification, VerificationCheck

# ---------- helpers ----------
_NOT_FOUND_RE = re.compile(
    r"couldn'?t find|could not find|not (?:found )?in the (?:plant |provided )?documentation|"
    r"not covered in the (?:provided )?(?:docs|documentation|excerpts)|"
    r"(?:can'?t|cannot|unable to|won'?t) (?:help|assist)|doesn'?t look like a plant documentation",
    re.I,
)


def is_exempt_text(answer: str) -> bool:
    """Not-found / refusal replies carry no citations or figures."""
    return bool(_NOT_FOUND_RE.search(answer))


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?;])\s+|\n+", text) if s.strip()]


# ---------- a. citation validity ----------
_CITE_RE = re.compile(r"\[([^\[\]§]+?)\s*§\s*([^\[\]]+?)\]")
_SECNUM_RE = re.compile(r"\d+(?:\.\d+)*")


def _chunk_sections(c: RetrievedChunk) -> list[str]:
    nums = []
    for seg in c.section_path.split(">"):
        m = re.match(r"\s*(\d+(?:\.\d+)*)", seg)
        if m:
            nums.append(m.group(1))
    return nums


def _title_match(cited: str, c: RetrievedChunk) -> bool:
    ct = _norm(cited)
    if not ct:
        return False
    for t in (_norm(c.title), _norm(c.section_path.split(">")[0])):
        if t and (ct in t or t in ct):
            return True
    return False


def _sec_match(sec: str, c: RetrievedChunk) -> bool:
    nums = _chunk_sections(c)
    want = _SECNUM_RE.findall(sec)
    if not want:
        return _norm(sec) in _norm(c.section_path)
    for w in want:
        if not any(n == w or n.startswith(w + ".") or w.startswith(n + ".") for n in nums):
            return False
    return True


def check_citations(answer: str, chunks: list[RetrievedChunk], exempt: bool) -> VerificationCheck:
    cites = _CITE_RE.findall(answer)
    if not cites:
        if exempt:
            return VerificationCheck(name="citation_validity", passed=True, detail="no citations needed")
        return VerificationCheck(name="citation_validity", passed=False, detail="answer has no citations")
    bad = []
    for title, sec in cites:
        if not any(_title_match(title, c) and _sec_match(sec, c) for c in chunks):
            bad.append(f"[{title.strip()} §{sec.strip()}]")
    if bad:
        return VerificationCheck(
            name="citation_validity",
            passed=False,
            detail="citation not matching a retrieved excerpt: " + ", ".join(bad),
        )
    return VerificationCheck(name="citation_validity", passed=True, detail=f"{len(cites)} citation(s) valid")


# ---------- b. numeric grounding ----------
_UNITS = (
    r"N\s*[·.\-⋅•*]?\s*m|Nm|lbf\s*[·.\-⋅•*]?\s*ft|ft\s*[·.\-⋅•*]?\s*lbf|mm|cm|km|kg|mg|psi|kpa|mpa|bar|"
    r"minutes?|mins?|hours?|hrs?|days?|weeks?|seconds?|secs?|%|percent|gpm|lpm|rpm|hp|kw|hz|"
    r"ft|feet|inch(?:es)?|in\.|lbs?|g|V|volts?|amps?|ohms?|°\s*[CF]|deg(?:rees)?\s*[CF]"
)
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_VAL_UNIT_RE = re.compile(
    rf"(?<![\w.§])(?P<a>{_NUM})(?:\s*(?:-|–|—|to)\s*(?P<b>{_NUM}))?\s*(?P<u>{_UNITS})(?![A-Za-z0-9])",
    re.I,
)
_ANYNUM_RE = re.compile(_NUM)
_UNIT_CANON = [
    (r"^n\s*[·.\-⋅•*]?\s*m$", "nm"),
    (r"^lbf\s*[·.\-⋅•*]?\s*ft$|^ft\s*[·.\-⋅•*]?\s*lbf$", "lbfft"),
    (r"^(minutes?|mins?)$", "min"),
    (r"^(hours?|hrs?)$", "hr"),
    (r"^(seconds?|secs?)$", "sec"),
    (r"^(%|percent)$", "%"),
    (r"^(ft|feet)$", "ft"),
    (r"^(inch(es)?|in\.)$", "in"),
    (r"^(volts?|v)$", "v"),
    (r"^lbs?$", "lb"),
    (r"^amps?$", "a"),
    (r"^ohms?$", "ohm"),
    (r"^days?$", "day"),
    (r"^weeks?$", "week"),
]


def _canon_unit(u: str) -> str:
    u = re.sub(r"\s+", " ", u.strip().lower())
    m = re.match(r"^(?:°|deg(?:rees)?)\s*([cf])$", u)
    if m:
        return "deg" + m.group(1)
    for pat, out in _UNIT_CANON:
        if re.match(pat, u):
            return out
    return u


def _canon_num(n: str) -> str:
    n = n.replace(",", "")
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n


def _pairs(text: str) -> set[tuple[str, str]]:
    out = set()
    for m in _VAL_UNIT_RE.finditer(text):
        u = _canon_unit(m.group("u"))
        out.add((_canon_num(m.group("a")), u))
        if m.group("b"):
            out.add((_canon_num(m.group("b")), u))
    return out


def check_numbers(answer: str, chunks: list[RetrievedChunk], exempt: bool) -> VerificationCheck:
    claimed = _pairs(_CITE_RE.sub(" ", answer))
    if not claimed:
        return VerificationCheck(name="numeric_grounding", passed=True, detail="no figures with units")
    ctx = "\n".join(c.content for c in chunks)
    ctx_pairs = _pairs(ctx)
    ctx_vals = {_canon_num(n) for n in _ANYNUM_RE.findall(ctx)}
    ctx_units = {u for _, u in ctx_pairs}
    bad = []
    for v, u in sorted(claimed):
        if (v, u) in ctx_pairs:
            continue
        if v in ctx_vals and u in ctx_units:  # table-style: value and unit appear separately
            continue
        bad.append(f"{v} {u}")
    if bad:
        return VerificationCheck(
            name="numeric_grounding", passed=False, detail="figures not found in excerpts: " + ", ".join(bad)
        )
    return VerificationCheck(name="numeric_grounding", passed=True, detail=f"{len(claimed)} figure(s) grounded")


# ---------- c. forbidden advice ----------
_STRONG_VERB = (
    r"bypass\w*|by-pass\w*|defeat\w*|jumper\w*|jump\s+out|circumvent\w*|disabl\w*|disarm\w*|"
    r"overrid\w*|cheat\w*|tap(?:e|ing)\s+over|wir(?:e|ing)\s+around|tamper\w*"
)
_REMOVE_VERB = r"remov\w*|tak(?:e|ing)\s+off|pull(?:ing)?\s+out"
_DEVICE_ALL = (
    r"interlocks?|light\s+curtains?|(?:machine\s+|safety\s+)?guards?|guarding|e-?\s?stops?|emergency\s+stops?|"
    r"lock-?\s?out|tag-?\s?out|loto|safety\s+(?:devices?|switch(?:es)?|sensors?|systems?|circuits?)"
)
_DEVICE_CORE = (
    r"interlocks?|light\s+curtains?|e-?\s?stops?|emergency\s+stops?|"
    r"safety\s+(?:devices?|switch(?:es)?|sensors?|circuits?)"
)
_NEGATION = re.compile(
    r"\b(never|do not|don'?t|must not|mustn'?t|not permitted|not allowed|prohibited|forbidden|cannot|can'?t|"
    r"shall not|may not|not be|is not|are not|no one|nobody|illegal|won'?t|refuse|unable to)\b",
    re.I,
)
_STRONG_RE = re.compile(
    rf"\b(?:{_STRONG_VERB})\b.*\b(?:{_DEVICE_ALL})\b|\b(?:{_DEVICE_ALL})\b.*\b(?:{_STRONG_VERB})\b", re.I
)
_REMOVE_RE = re.compile(rf"\b(?:{_REMOVE_VERB})\b.*\b(?:{_DEVICE_CORE})\b", re.I)


def check_forbidden(answer: str) -> VerificationCheck:
    for s in _split_sentences(answer):
        if _NEGATION.search(s):
            continue
        if _STRONG_RE.search(s) or _REMOVE_RE.search(s):
            return VerificationCheck(
                name="forbidden_advice", passed=False, detail=f"unsafe instruction: {s.strip()[:140]}"
            )
    return VerificationCheck(name="forbidden_advice", passed=True, detail="no unsafe instructions")


# ---------- d. safety tie-in ----------
_PHYSICAL_RE = re.compile(
    r"\b(replac\w*|remov\w*|open\w*|clear\w*|enter\w*|bypass\w*|repair\w*|disassembl\w*|weld\w*|"
    r"install\w*|adjust\w*|servic\w*|chang\w*|unjam\w*|jam\w*|tighten\w*|clean\w*|lubricat\w*|"
    r"swap\w*|unclog\w*|rebuild\w*|reassembl\w*|grease\w*)\b",
    re.I,
)
_SAFETY_RE = re.compile(r"lock-?\s?out|tag-?\s?out|\bLOTO\b|safety\s*:", re.I)


def check_safety_tie_in(answer: str, question: str, exempt: bool) -> VerificationCheck:
    if exempt or not _PHYSICAL_RE.search(question):
        return VerificationCheck(name="safety_tie_in", passed=True, detail="not required")
    if _SAFETY_RE.search(answer):
        return VerificationCheck(name="safety_tie_in", passed=True, detail="safety/lockout line present")
    return VerificationCheck(
        name="safety_tie_in", passed=False, detail="physical work without lockout/tagout or Safety: line"
    )


# ---------- entry point ----------
def verify(
    answer: str, chunks: list[RetrievedChunk], question: str, decision: RouteDecision | None = None
) -> Verification:
    exempt = is_exempt_text(answer)
    checks = [
        check_citations(answer, chunks, exempt),
        check_numbers(answer, chunks, exempt),
        check_forbidden(answer),
        check_safety_tie_in(answer, question, exempt),
    ]
    return Verification(passed=all(c.passed for c in checks), checks=checks)
