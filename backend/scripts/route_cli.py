"""Run the router over the example set: uv run python scripts/route_cli.py [--model M]"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routing.router import route  # noqa: E402
from app.routing.sources import EXAMPLES  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    ok = 0
    lat = []
    for q, expected in EXAMPLES:
        d = route(q, model=args.model)
        got = d.searched or ["none"]
        # correct = top-searched label expected AND all expected labels covered (extras tolerated;
        # the physical-verb rule legitimately adds safety)
        good = got[0] in expected and set(expected) <= set(got)
        ok += good
        lat.append(d.latency_ms)
        flag = "OK " if good else "BAD"
        print(f"{flag} {q[:55]:55} pred={','.join(got):24} exp={'+'.join(expected)}{' [fallback]' if d.fallback else ''}")
    print(f"\nmodel={args.model or d.model} accuracy={ok}/{len(EXAMPLES)} ({ok / len(EXAMPLES):.0%}) avg_latency={sum(lat) / len(lat):.0f}ms")


if __name__ == "__main__":
    main()
