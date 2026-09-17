"""Narrow, reproducible reply checks; these do not establish factual support."""

import re
from functools import lru_cache
from typing import Literal

from pydantic_core import PydanticCustomError


@lru_cache(maxsize=256)
def compile_reply_pattern(pattern: str) -> re.Pattern[str]:
    """Compile bounded regexes without groups, backreferences or unbounded repeats."""
    if not pattern or len(pattern) > 512:
        raise PydanticCustomError("invalid_reply_pattern", "Reply patterns must contain 1..512 characters")
    # Strip character classes and escapes before inspecting regex operators.
    operators = re.sub(r"\[(?:\\.|[^\]\\])*\]|\\[^0-9]", "x", pattern)
    repeats = tuple((match.group(1), match.group(2)) for match in re.finditer(r"\{(\d+)(?:,(\d+))?\}", operators))
    bounded = re.sub(r"\{\d+(?:,\d+)?\}", "", operators)
    if any(char in bounded for char in "()*+?{}\\") or len(repeats) > 2:
        raise PydanticCustomError("invalid_reply_pattern", "Only literals, classes, alternatives and at most two bounded repeats are supported")
    if any(int(low) > int(high or low) or int(high or low) > 64 for low, high in repeats):
        raise PydanticCustomError("invalid_reply_pattern", "Reply repeat bounds must be ordered and at most 64")
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise PydanticCustomError("invalid_reply_pattern", "Invalid reply regex") from exc
    if compiled.search("") is not None:
        raise PydanticCustomError("invalid_reply_pattern", "Reply patterns must not match empty text")
    return compiled


def policy_violations(text: str, patterns: tuple[str, ...]) -> tuple[str, ...]:
    """Return exact matched dataset patterns, not a general policy judgement."""
    if len(text) > 16_000:
        return ("reply-exceeds-policy-check-limit",)
    return tuple(pattern for pattern in patterns if compile_reply_pattern(pattern).search(text))


def language_correct(text: str, expected: Literal["zh", "en"] | None) -> bool | None:
    """A coarse script check; English forbids CJK prose, Chinese requires CJK."""
    if expected is None:
        return None
    han = len(re.findall(r"[\u3400-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return {"zh": han > 0, "en": latin > 0 and han == 0}[expected]
