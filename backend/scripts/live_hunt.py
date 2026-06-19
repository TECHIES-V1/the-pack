"""Drive one real hunt end to end and verify the whole chain.

REST commands → engine → Postgres (source of truth) → outbox relay → Redis → gateway → WS.
This connects to the gateway WebSocket, runs a hunt with the two human gates (approve plan,
resolve hold), and checks the stream is dense, terminal, and carries real Qwen spend.

    python scripts/live_hunt.py ["your task here"]
"""

from __future__ import annotations

import asyncio
import json
import sys

import httpx
import websockets

ENGINE = "http://localhost:8000"
WS = "ws://localhost:8080"


async def main(task: str) -> int:
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.post(f"{ENGINE}/hunts", json={"input": task, "source": "typed"})
        r.raise_for_status()
        hunt_id = r.json()["hunt_id"]
        print(f"hunt: {hunt_id}")

        events: list[dict] = []
        approved = False

        # ping_interval=None: a hunt can sit idle while a thinking-mode wolf streams; don't let
        # the client's own keepalive drop the long-lived stream (prod nginx uses a 3600s read
        # timeout for the same reason).
        async with websockets.connect(
            f"{WS}/hunts/{hunt_id}/stream?from_seq=0", ping_interval=None
        ) as ws:
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=120)
                except asyncio.TimeoutError:
                    print("!! timed out waiting for the next event")
                    return 1

                ev = json.loads(raw)
                events.append(ev)
                t = ev["type"]
                print(f"  seq {ev['seq']:>3}  {t:<16} {ev['actor']}")

                if t == "plan_proposed" and not approved:
                    approved = True
                    await http.post(
                        f"{ENGINE}/hunts/{hunt_id}/plan/approve",
                        json={"mode": "on_signal", "boundary_usd": 1.0},
                    )
                elif t == "hold_opened":
                    p = ev["payload"]
                    await http.post(
                        f"{ENGINE}/hunts/{hunt_id}/holds/{p['hold_id']}/resolve",
                        json={"resolution": p.get("recommended") or p["options"][0]},
                    )
                elif t in ("hunt_completed", "hunt_failed", "hunt_stopped"):
                    break

        # Verify.
        seqs = [e["seq"] for e in events]
        spend = [e for e in events if e["type"] == "tokens_spent"]
        cumulative = spend[-1]["payload"]["cumulative_usd"] if spend else 0.0
        snap = (await http.get(f"{ENGINE}/hunts/{hunt_id}")).json()

        print("\n--- summary ---")
        print(f"events streamed : {len(events)}")
        print(f"seq dense 0..N  : {seqs == list(range(len(seqs)))}")
        print(f"engine last_seq : {snap['last_seq']}  (== {len(events) - 1}? {snap['last_seq'] == len(events) - 1})")
        print(f"tokens_spent ev : {len(spend)}   cumulative ${cumulative}")
        print(f"final state     : {snap['state']}")
        ok = (
            seqs == list(range(len(seqs)))
            and events[-1]["type"] == "hunt_completed"
            and cumulative > 0
            and snap["last_seq"] == len(events) - 1
        )
        print(f"RESULT          : {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "Brief me on the BNPL market in Nigeria."
    raise SystemExit(asyncio.run(main(task)))
