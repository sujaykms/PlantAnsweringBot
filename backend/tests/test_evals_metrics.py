"""Unit tests for deterministic eval metrics and golden-set integrity (fast, no network/LLM)."""

import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from evals import metrics as M  # noqa: E402

CHUNKS = [
    {"title": "SOP-07 Lockout/Tagout (Hazardous Energy Control)",
     "section_path": "SOP-07 Lockout/Tagout (Hazardous Energy Control) > 4 Special Situations > 4.3 Minor Servicing Exception"},
    {"title": "MM-P101 Centrifugal Pump P-101 Maintenance Manual",
     "section_path": "MM-P101 Centrifugal Pump P-101 Maintenance Manual > 5 Alignment and Torque Specifications"},
]
PAIRS = [(c["title"], c["section_path"]) for c in CHUNKS]


@pytest.mark.parametrize("ans", ["Torque is 95 N·m.", "95 N-m", "95 Nm", "95 N m", "**95 N·m**"])
def test_exact_value_unit_variants(ans):
    assert M.value_present("95 N·m", ans)


def test_exact_value_boundaries_and_unicode():
    assert not M.value_present("5.5", "limit is 15.5 mm")
    assert not M.value_present("10 mm", "110 mm")
    assert M.value_present("0.05 mm", "must be ≤ 0.05 mm")
    assert M.value_present("≤ 0.05 mm", "<= 0.05 mm")
    assert M.exact_values_score([], "x") is None
    assert M.exact_values_score(["85 N·m", "9 N·m"], "85 N-m only") == 0.5


def test_recall_and_mrr_math():
    ranks = [1, 2, None, 7]
    assert M.recall_at_k(ranks, 6) == pytest.approx(0.5)
    assert M.recall_at_k(ranks, 1) == pytest.approx(0.25)
    assert M.mrr(ranks) == pytest.approx((1 + 0.5 + 1 / 7) / 4)
    assert M.recall_at_k([], 6) == 0.0 and M.mrr([]) == 0.0


def test_chunk_matching():
    assert M.first_hit_rank(PAIRS, "SOP-07", "4.3 Minor") == 1
    assert M.first_hit_rank(PAIRS, "MM-P101", "5 Alignment|4 Mech") == 2
    assert M.first_hit_rank(PAIRS, "SOP-12") is None
    # section is matched after the title, so a title substring does not leak into the section match
    assert not M.chunk_matches("MM-P101 X", "MM-P101 X > 2 Foo", "MM-P101", "P101")
    # paired alternatives
    assert M.chunk_matches("MM-CNV x", "MM-CNV x > 5 Torque", "MM-P101|MM-CNV", "2 Pre|5 Torque")
    assert not M.chunk_matches("MM-CNV x", "MM-CNV x > 2 Pre", "MM-P101|MM-CNV", "2 Pre|5 Torque")


def test_citation_validity():
    ok = "Never bypass [SOP-07 Lockout/Tagout §4.3]. Torque [MM-P101 Centrifugal Pump P-101 Maintenance Manual §5]."
    assert M.citation_score(ok, CHUNKS) == {"n": 2, "valid": 2}
    assert M.citation_score("See [SOP-07 §4.3, §4].", CHUNKS) == {"n": 1, "valid": 1}
    bad = "[SOP-07 §9.9] and [SOP-99 §4.3] and [MM-P101 §4]"
    assert M.citation_score(bad, CHUNKS) == {"n": 3, "valid": 0}
    assert M.citation_score("no citations here", CHUNKS) == {"n": 0, "valid": 0}


def test_refusal_heuristics():
    assert M.says_not_found("I couldn't find this in the plant documentation.")
    assert M.says_not_found("whatever", True)
    assert not M.says_not_found("Torque is 95 N·m.")
    good = "Bypassing light curtains is never permitted. Clear the obstruction and apply lockout."
    assert M.refusal_ok(good)["ok"]
    bad = "Sure:\n1. Jumper the interlock switch\n2. Close the door"
    assert M.refusal_ok(bad)["gives_steps"] and not M.refusal_ok(bad)["ok"]
    assert not M.refusal_ok("Answer ONLY from the provided documentation. never.")["ok"]


def test_threshold_sweep_and_best_cutoff():
    scores = [-10.0, -9.0, -2.0, -1.0, None]
    nf = [True, True, False, False, True]
    rows = M.threshold_sweep(scores, nf, [-9.5, -5.0, 0.0])
    assert rows[0]["tp"] == 2 and rows[0]["fp"] == 0 and rows[0]["fn"] == 1  # None counts as not found
    assert rows[1]["f1"] == pytest.approx(1.0)
    assert rows[2]["fp"] == 2
    assert M.best_cutoff(rows)["cutoff"] == -5.0
    assert M.prf(0, 0, 0) == (0.0, 0.0, 0.0)


def test_parse_sse_tolerates_new_events():
    lines = ["event: status\r", 'data: {"stage":"retrieving"}\r', "\r", "event: token", 'data: {"text":"hi"}', "", ": ping", ""]
    assert M.parse_sse(lines) == [("status", '{"stage":"retrieving"}'), ("token", '{"text":"hi"}')]


# ---------------- golden set integrity ----------------
GOLD = M.load_golden()
DOCS = {p: unicodedata.normalize("NFKC", p.read_text()) for p in (ROOT / "docs").glob("*/*.md")}
ALL_TEXT = "\n".join(DOCS.values())
FIELDS = {"id", "question", "category", "expected_routes", "gold_doc", "gold_section", "key_facts",
          "exact_values", "should_not_find", "expect_emergency", "expect_refusal_or_safe", "reviewed"}


def test_golden_shape():
    assert 75 <= len(GOLD) <= 90
    assert len({g["id"] for g in GOLD}) == len(GOLD)
    for g in GOLD:
        assert set(g) == FIELDS, g["id"]
        assert set(g["expected_routes"]) <= {"safety", "maintenance", "quality", "analytics", "none"}
        assert g["reviewed"] is False


def test_golden_exact_values_appear_in_docs():
    missing = [(g["id"], v) for g in GOLD for v in g["exact_values"] if not M.value_present(v, ALL_TEXT)]
    assert not missing, missing


def test_golden_gold_docs_exist_in_docs():
    titles = [re.search(r"^title: (.*)$", t, re.M).group(1).lower() for t in DOCS.values()]
    for g in GOLD:
        for d in M._alts(g["gold_doc"]):
            assert any(d in t for t in titles), (g["id"], d)
