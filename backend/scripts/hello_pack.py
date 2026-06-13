"""hello-pack — the seam demo (Doc 04 §7, due Jun 12).

One fake hunt: the engine pushes fixture events into Redis and the gateway tails them out
to a browser, end to end through real infrastructure. Proves the seam on day 3.

Usage:
    python scripts/hello_pack.py [fixture_name] [--delay 0.4]

    fixture_name defaults to flow_a_researcher. It is resolved against ../fixtures/.

Run `docker compose up redis` first (or point REDIS_URL at Tair), then start the gateway
and open a WS client on /hunts/<hunt_id>/stream?from_seq=0.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import redis.asyncio as redis

from app.config import settings

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def stream_key(hunt_id: str) -> str:
    return f"hunt:{hunt_id}:events"


async def main(fixture: str, delay: float) -> None:
    path = FIXTURES_DIR / fixture
    if not path.exists() and (FIXTURES_DIR / f"{fixture}.jsonl").exists():
        path = FIXTURES_DIR / f"{fixture}.jsonl"
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    r = redis.from_url(settings.redis_url, decode_responses=True)
    hunt_id = json.loads(lines[0])["hunt_id"]
    key = stream_key(hunt_id)
    await r.delete(key)

    print(f"hello-pack: pushing {len(lines)} events to {key} (delay={delay}s)")
    for ln in lines:
        ev = json.loads(ln)
        await r.xadd(key, {"event": ln})
        print(f"  seq {ev['seq']:>3}  {ev['type']}  ({ev['actor']})")
        await asyncio.sleep(delay)

    print(f"hello-pack: done. Tail it from the gateway: /hunts/{hunt_id}/stream?from_seq=0")
    await r.aclose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("fixture", nargs="?", default="flow_a_researcher.jsonl")
    ap.add_argument("--delay", type=float, default=0.4)
    args = ap.parse_args()
    asyncio.run(main(args.fixture, args.delay))
