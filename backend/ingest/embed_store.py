"""Idempotent document upsert: hash check, chunk replace, single transaction."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pgvector import Vector
from psycopg_pool import ConnectionPool

from app.contracts import ChunkIn, DocSource
from app.embeddings import embed_passages


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def existing_sha(pool: ConnectionPool, db_path: str) -> str | None:
    with pool.connection() as conn:
        row = conn.execute("select sha256 from documents where path = %s", (db_path,)).fetchone()
    return row["sha256"] if row else None


def store_document(
    pool: ConnectionPool,
    *,
    db_path: str,
    source: DocSource,
    title: str,
    sha: str,
    chunks: list[ChunkIn],
) -> int:
    """Embed then replace the document's chunks in one transaction. Returns chunk count."""
    vectors: list[list[float]] = []
    for i in range(0, len(chunks), 64):
        vectors += embed_passages([c.embed_text for c in chunks[i : i + 64]])

    with pool.connection() as conn:  # commits on clean exit, rolls back on error
        row = conn.execute("select id from documents where path = %s", (db_path,)).fetchone()
        if row:
            doc_id = row["id"]
            conn.execute("delete from chunks where document_id = %s", (doc_id,))
            conn.execute(
                "update documents set source=%s, title=%s, sha256=%s, ingested_at=now() where id=%s",
                (source, title, sha, doc_id),
            )
        else:
            doc_id = conn.execute(
                "insert into documents (source, title, path, sha256) values (%s,%s,%s,%s) returning id",
                (source, title, db_path, sha),
            ).fetchone()["id"]
        with conn.cursor() as cur:
            cur.executemany(
                """insert into chunks (document_id, source, section_path, page, doc_type,
                       equipment_ids, content, embed_text, embedding)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                [
                    (doc_id, c.source, c.section_path, c.page, c.doc_type,
                     c.equipment_ids, c.content, c.embed_text, Vector(v))
                    for c, v in zip(chunks, vectors)
                ],
            )
    return len(chunks)
