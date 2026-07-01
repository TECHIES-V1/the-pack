"""Alpha intake and chat helpers — prompts, heuristics, and the SSE token stream.

Used only by routers/hunts.py; isolated here to keep the route file focused on HTTP concerns.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import re

from fastapi import Request

# ---------------------------------------------------------------------------
# Alpha's intake gate — clarify until there is a real, actionable task
# ---------------------------------------------------------------------------

ALPHA_INTAKE = (
    "You are Alpha, the leader of the Pack, talking with the Packmaster. You're warm, sharp, "
    "plain-spoken, calm and quietly confident, with a light touch of wit. You chat like a "
    "genuinely helpful, intelligent person — a real conversation, never a form.\n"
    "Respond with ONLY a JSON object, no prose around it: "
    '{"reply": string, "ready": boolean, "brief": string}.\n'
    "\n"
    "Writing `reply` (this is what makes you feel smart, not robotic):\n"
    "- Lead with the actual answer, then add only what's genuinely useful — substantive but easy "
    "to read. Say exactly as much as the moment needs: a quick fact is a sentence; a real question "
    "deserves a few. Don't pad, don't ramble, and don't be clipped or curt.\n"
    "- Format for easy reading. When the answer is a set of items, options, or steps, use a short "
    "Markdown bullet list ('- ' lines) with the key term in **bold**; otherwise write natural "
    "prose. Leave a blank line between distinct ideas. Keep it conversational, not a wall.\n"
    "- Sound human and present-tense. First person ('I', 'me') is good; a little warmth and "
    "personality is welcome. No jargon, no robotic filler, no repeating 'name a task'.\n"
    "- When you need something from them, end with ONE natural question — never a stack.\n"
    "\n"
    "Launching the Pack (`ready`):\n"
    "- ready=true when they ask you to find, research, look up, gather, compare, write, draft, "
    "review, summarize, analyze, or dig something up — anything needing real work or looking "
    "things up, even if it needs current or web info (the Pack does the looking, so never decline "
    "of data). Then `brief` = one crisp sentence naming the job, and `reply` names what you'll go "
    "do in your own warm words, scoped concretely so they know exactly what's coming.\n"
    '- otherwise ready=false and brief="": greetings, questions about you, general chat, thinking '
    "out loud, or a simple fact you can just answer. Be a good conversationalist.\n"
    "If your reply says you'll go do something now, ready MUST be true.\n"
    "\n"
    "Examples:\n"
    'User: "hi" → {"reply": "Hey — good to see you. I\'m Alpha; I run the Pack, so whatever '
    'you\'re chasing, I can put a team on it. What are you working on?", "ready": false, '
    '"brief": ""}\n'
    'User: "who are you?" → {"reply": "I\'m Alpha, the lead of the Pack — think of me as your '
    "point person. You tell me what you need looked into, written, or sorted out, and I send a "
    'coordinated team after it while you watch it happen. What can I get started on?", '
    '"ready": false, "brief": ""}\n'
    'User: "what is the capital of France?" → {"reply": "Paris — and it\'s been the seat of '
    'French power for centuries. Want me to dig into anything about it?", "ready": false, '
    '"brief": ""}\n'
    'User: "research the BNPL market in Nigeria and write me a brief" → {"reply": "Got it — I\'ll '
    "put the pack on Nigeria's BNPL market: who's leading, what the regulators are doing, and pull "
    'it into a clean brief for you. Ready when you are.", "ready": true, "brief": "Research the '
    'BNPL market in Nigeria — key players and regulation — and write a brief."}'
)

# Alpha's CHAT voice — deliberately NOT the internal orchestrator prompt (Doc 02 §08).
ALPHA_CHAT = (
    "You are Alpha, leader of the Pack, talking to the Packmaster. Answer in plain English, "
    "present tense, warm and brief — 2 to 4 sentences. Never mention any internal machinery: "
    "no tokens, models, prompts, agents, ledgers, gates, plans-as-lists, or jargon of any kind. "
    "Do not dump checklists or step plans. Just answer the question helpfully and naturally."
)

_GREETINGS = {
    "hi", "hii", "hey", "hello", "yo", "sup", "hiya", "howdy", "ok", "okay",
    "thanks", "thank you", "good morning", "good afternoon", "good evening",
    "wassup", "whatsup",
}

_QUESTION_STARTS = {
    "who", "what", "why", "how", "when", "where", "which", "can",
    "could", "do", "does", "is", "are", "should", "would", "will",
}

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def looks_like_task(text: str) -> bool:
    """Offline heuristic for the clarify-gate when there's no model: greetings, questions, and bare
    fragments aren't tasks; a longer imperative is treated as actionable."""
    raw = text.strip()
    t = raw.lower().rstrip("!.?")
    if not t or t in _GREETINGS or raw.endswith("?"):
        return False
    words = t.split()
    if words[0] in _QUESTION_STARTS:
        return False
    return len(words) >= 3


def last_user(messages: list[dict]) -> str:
    return next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")


def parse_intake(text: str) -> dict | None:
    """Pull intake JSON out of the model reply, tolerating a stray fence or prose around it.
    Returns None if there's no usable object — callers MUST NOT launch on None."""
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1]
    for candidate in (text, text[text.find("{") : text.rfind("}") + 1] if "{" in text else ""):
        try:
            # strict=False: models routinely put real newlines inside string values.
            obj = json.loads(candidate, strict=False)
            if isinstance(obj, dict) and "ready" in obj:
                return obj
        except json.JSONDecodeError:
            continue
    return None


def safe_reply(text: str) -> str:
    """A reply for when intake JSON can't be parsed — never leak raw braces into the chat."""
    if text.strip().startswith("{") or '"reply"' in text:
        m = re.search(r'"reply"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if m:
            try:
                return json.loads(f'"{m.group(1)}"')
            except json.JSONDecodeError:
                pass
        return "Tell me what you want the pack to hunt down."
    return text or "Tell me what you want the pack to hunt down."


async def stream_tokens(queue: asyncio.Queue, request: Request):
    """Yield SSE `token` frames from the queue until the None sentinel, with ~15s heartbeats
    and early exit on client disconnect so a vanished client can't pin a task forever.

    Disconnect is checked on EVERY token (not just at the heartbeat) so a closed tab stops
    billing within one token round-trip rather than up to 15 seconds later.
    """
    while True:
        try:
            delta = await asyncio.wait_for(queue.get(), timeout=15.0)
        except TimeoutError:
            if await request.is_disconnected():
                return
            yield ": keep-alive\n\n"
            continue
        if delta is None:
            return
        if await request.is_disconnected():
            return
        yield f"data: {json.dumps({'type': 'token', 'text': delta})}\n\n"


async def cancel_task(task: asyncio.Task) -> None:
    if not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
