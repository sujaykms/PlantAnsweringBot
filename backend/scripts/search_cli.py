"""uv run python scripts/search_cli.py "<query>" [--sources safety,quality]"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contracts import DOC_SOURCES  # noqa: E402
from app.retrieval import retrieve  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--sources", default=",".join(DOC_SOURCES))
    args = ap.parse_args()
    for c in retrieve(args.query, args.sources.split(",")):
        print(f"{c.rerank_score:7.2f}  {c.source:11} {c.section_path}  (rrf {c.score:.4f})")


if __name__ == "__main__":
    main()
