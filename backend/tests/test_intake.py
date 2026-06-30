"""Unit tests for the intake gate heuristics and reply helpers in app/core/intake.py.

Pure functions — no I/O, no event loop required.
"""

from __future__ import annotations

from app.core.intake import looks_like_task, parse_intake, safe_reply

# ---------------------------------------------------------------------------
# looks_like_task
# ---------------------------------------------------------------------------


def test_greeting_is_not_a_task() -> None:
    for text in ("hi", "hey", "hello", "thanks", "ok", "wassup"):
        assert looks_like_task(text) is False, f"'{text}' should not be a task"


def test_question_is_not_a_task() -> None:
    for text in (
        "what do you think about X?",
        "who are you?",
        "can you help me?",
        "how does this work?",
    ):
        assert looks_like_task(text) is False, f"'{text}' should not be a task"


def test_too_short_is_not_a_task() -> None:
    assert looks_like_task("BNPL") is False
    assert looks_like_task("write this") is False  # only 2 words


def test_clear_task_is_detected() -> None:
    for text in (
        "research the EV battery market for me",
        "write a brief on the BNPL market in Nigeria",
        "find the top ten fintechs in Africa",
        "summarise the latest IMF report on emerging markets",
        "compare solid-state vs lithium-ion battery costs",
    ):
        assert looks_like_task(text) is True, f"'{text}' should be a task"


# ---------------------------------------------------------------------------
# parse_intake
# ---------------------------------------------------------------------------


def test_parse_clean_json() -> None:
    raw = '{"reply": "On it!", "ready": true, "brief": "Research BNPL in Nigeria."}'
    result = parse_intake(raw)
    assert result is not None
    assert result["ready"] is True
    assert result["brief"] == "Research BNPL in Nigeria."


def test_parse_json_with_prose_wrapper() -> None:
    raw = 'Sure! Here you go: {"reply": "Let\'s go.", "ready": true, "brief": "A task."}'
    result = parse_intake(raw)
    assert result is not None
    assert result["ready"] is True


def test_parse_json_with_code_fence() -> None:
    raw = "```json\n{\"reply\": \"OK\", \"ready\": false, \"brief\": \"\"}\n```"
    result = parse_intake(raw)
    assert result is not None
    assert result["ready"] is False


def test_parse_chat_response_ready_false() -> None:
    raw = '{"reply": "Hey there!", "ready": false, "brief": ""}'
    result = parse_intake(raw)
    assert result is not None and result["ready"] is False


def test_parse_returns_none_on_garbage() -> None:
    assert parse_intake("totally not JSON here") is None
    assert parse_intake("") is None
    assert parse_intake("[1, 2, 3]") is None  # no "ready" key


def test_parse_real_newlines_in_strings() -> None:
    """Models often embed literal newlines inside string values — strict=False handles this."""
    raw = '{"reply": "Line one.\nLine two.", "ready": false, "brief": ""}'
    result = parse_intake(raw)
    assert result is not None
    assert "Line one." in result["reply"]


# ---------------------------------------------------------------------------
# safe_reply
# ---------------------------------------------------------------------------


def test_safe_reply_passthrough_on_plain_text() -> None:
    assert safe_reply("Hello pack") == "Hello pack"
    assert safe_reply("Just a normal sentence.") == "Just a normal sentence."


def test_safe_reply_no_raw_braces_on_json_blobs() -> None:
    raw_json = '{"reply": "Here we go!", "ready": false, "brief": ""}'
    result = safe_reply(raw_json)
    assert "{" not in result
    assert "Here we go!" in result


def test_safe_reply_fallback_on_unparseable_json_blob() -> None:
    # A brace-started string that can't be parsed falls back to the default.
    result = safe_reply("{broken json}")
    assert "{" not in result
    assert len(result) > 5  # not empty


def test_safe_reply_empty_gives_default() -> None:
    result = safe_reply("")
    assert len(result) > 5
    assert "{" not in result
