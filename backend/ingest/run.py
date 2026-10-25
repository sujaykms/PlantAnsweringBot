"""CLI: uv run python -m ingest.run [--path docs] [--force]"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.contracts import DOC_SOURCES
from app.db import get_pool

from ingest.chunker import chunk_document
from ingest.embed_store import existing_sha, sha256_file, store_document
from ingest.parse import parse_file


def find_docs_root(arg: str) -> Path:
    p = Path(arg)
    if p.is_dir():
        return p.resolve()
    # allow running from backend/ with the repo-level docs dir
    alt = Path(__file__).resolve().parents[2] / arg
    if alt.is_dir():
        return alt
    raise SystemExit(f"docs path not found: {arg}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="docs")
    ap.add_argument("--force", action="store_true", help="re-ingest even if unchanged")
    args = ap.parse_args()

    root = find_docs_root(args.path)
    pool = get_pool()
    for source in DOC_SOURCES:
        for f in sorted((root / source).glob("*")) if (root / source).is_dir() else []:
            if f.suffix.lower() not in {".md", ".pdf"}:
                continue
            db_path = f.relative_to(root.parent).as_posix()
            sha = sha256_file(f)
            if not args.force and existing_sha(pool, db_path) == sha:
                print(f"skipped   {db_path}")
                continue
            doc = parse_file(f)
            chunks = chunk_document(doc, source)
            n = store_document(
                pool, db_path=db_path, source=source, title=doc.title or f.stem, sha=sha, chunks=chunks
            )
            print(f"ingested  {db_path}: {n} chunks")

    with pool.connection() as conn:
        rows = conn.execute(
            "select source, count(*) n, count(distinct document_id) d from chunks group by 1 order by 1"
        ).fetchall()
    print("--- totals ---")
    for r in rows:
        print(f"{r['source']:<12} {r['n']:>4} chunks / {r['d']} docs")
    pool.close()


if __name__ == "__main__":
    main()
