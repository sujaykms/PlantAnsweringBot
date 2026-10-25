from ingest.chunker import chunk_markdown, extract_equipment, row_sentences, tokens

DOC = """---
title: MM-X Test Manual
source: maintenance
doc_type: manual
---

# MM-X Test Manual

## 1 Overview

Pump P-101 feeds line 2. See SOP-07 and QS-12 and MM-P101.

## 2 Torque

| Fastener | Size | Torque |
|---|---|---|
| Motor mount bolts | M12 | 85 N·m |
| Guard screws | M6 | 9 N·m |

## 3 Repair

### 3.1 Replace Seal

Lockout per SOP-07 first.

1. Stop the pump.
2. Apply lock.
3. Remove guard.
"""


def by_path(chunks, frag):
    return [c for c in chunks if frag in c.section_path]


def test_section_path_format():
    chunks = chunk_markdown(DOC, "maintenance")
    paths = {c.section_path for c in chunks}
    assert "MM-X Test Manual > 3 Repair > 3.1 Replace Seal" in paths
    assert "MM-X Test Manual > 1 Overview" in paths


def test_embed_text_and_doc_type():
    c = by_path(chunk_markdown(DOC, "maintenance"), "1 Overview")[0]
    assert c.embed_text == f"[MAINTENANCE] {c.section_path}\n{c.content}"
    assert c.doc_type == "manual"


def test_procedure_kept_whole_with_lead_in():
    c = by_path(chunk_markdown(DOC, "maintenance"), "3.1")[0]
    assert "Lockout per SOP-07 first." in c.content
    assert all(f"{i}." in c.content for i in (1, 2, 3))


def test_long_procedure_split_between_steps_repeats_title():
    steps = "\n".join(f"{i}. " + "word " * 40 for i in range(1, 21))
    md = f"---\ntitle: T\ndoc_type: sop\n---\n# T\n\n## 1 Big Proc\n\n{steps}\n"
    chunks = chunk_markdown(md, "safety")
    assert len(chunks) > 1
    assert all(c.content.startswith("1 Big Proc") for c in chunks)
    assert all(tokens(c.content) <= 420 for c in chunks)


def test_table_chunk_and_sentences():
    t = by_path(chunk_markdown(DOC, "maintenance"), "2 Torque")[0]
    assert t.doc_type == "table"
    assert "| Fastener | Size | Torque |" in t.content
    assert "Motor mount bolts: size M12, torque 85 N·m" in t.content


def test_row_sentences_skip_blank_cells():
    assert row_sentences(["A", "B"], [["x", "—"]]) == ["x"]


def test_equipment_extraction_dedupes_and_excludes_doc_ids():
    assert extract_equipment("P-101 and CNV-3, P-101; SOP-07 QS-12 MM-P101") == ["P-101", "CNV-3"]
    c = by_path(chunk_markdown(DOC, "maintenance"), "1 Overview")[0]
    assert c.equipment_ids == ["P-101"]


def test_heading_only_sections_skipped():
    chunks = chunk_markdown(DOC, "maintenance")
    assert not by_path(chunks, "> 3 Repair") or all(
        c.section_path.endswith("3.1 Replace Seal") for c in by_path(chunks, "3 Repair")
    )
