"""Rules for decision-model states (Jev/Laya jaggedness): short, in words, treated as data."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

SOFT_TOKEN_LIMIT = 300  # aim for this or fewer
HARD_TOKEN_LIMIT = 1024  # Laya's hard limit
CHARS_PER_TOKEN = 4
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
MAX_NUMBERS = 3  # more raw numbers than this reads as a data dump, not words
MAX_DIGIT_SHARE = 0.15  # digits as a share of non-space characters

_INSTRUCTION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (
    r"ignore (?:all |any |the )?(?:previous|prior|above|earlier)",
    r"disregard (?:all |any |the )?(?:previous|prior|above|instructions)",
    r"\byou (?:must|should|have to|need to|are now)\b",
    r"\b(?:system|assistant|user)\s*:",
    r"\bnew instructions?\b",
    r"\boverride\b",
    r"\bact as\b",
    r"\bpretend\b",
    r"\bdo not (?:follow|obey)\b",
)]


@dataclass(frozen=True)
class StateIssue:
    severity: str  # "warn" | "error"
    code: str
    message: str


def estimate_tokens(text: str) -> int:
    return -(-len(text) // CHARS_PER_TOKEN)


def check_state(text: str) -> List[StateIssue]:
    """Warnings (and errors) for a state string; empty list means it follows the rules."""
    issues: List[StateIssue] = []
    tokens = estimate_tokens(text)
    if tokens > HARD_TOKEN_LIMIT:
        issues.append(StateIssue("error", "too_long", f"~{tokens} tokens exceeds the {HARD_TOKEN_LIMIT} hard limit"))
    elif tokens > SOFT_TOKEN_LIMIT:
        issues.append(StateIssue("warn", "long", f"~{tokens} tokens; aim for {SOFT_TOKEN_LIMIT} or fewer"))
    compact = re.sub(r"\s", "", text)
    digits = sum(c.isdigit() for c in compact)
    if len(_NUMBER.findall(text)) > MAX_NUMBERS or (compact and digits / len(compact) > MAX_DIGIT_SHARE):
        issues.append(StateIssue("warn", "digit_heavy", "state uses raw numbers; write them in words"))
    return issues


def has_errors(issues: List[StateIssue]) -> bool:
    return any(i.severity == "error" for i in issues)


def flag_instructions(text: str) -> List[str]:
    """Instruction-like snippets in peer-message text, for logging only (state is data, never obeyed)."""
    found: List[str] = []
    for pattern in _INSTRUCTION_PATTERNS:
        for match in pattern.finditer(text):
            found.append(match.group(0))
    return found


_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
         "seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def number_word(n: int) -> str:
    """0..999 (and negatives) in English words."""
    if n < 0:
        return "minus " + number_word(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        return f"{_ONES[hundreds]} hundred" + (f" {number_word(rest)}" if rest else "")
    raise ValueError("number_word supports |n| < 1000")


def words_for_offset(dx: int, dy: int, *, spell: bool = False) -> str:
    """Offset as a phrase: x grows east, y grows south, so (2, -3) is "3 north, 2 east".

    ``spell=True`` writes the counts as words ("three north, two east").
    """
    def count(n: int) -> str:
        return number_word(n) if spell else str(n)

    parts: List[Tuple[int, str]] = []
    if dy:
        parts.append((abs(dy), "north" if dy < 0 else "south"))
    if dx:
        parts.append((abs(dx), "east" if dx > 0 else "west"))
    if not parts:
        return "here"
    return ", ".join(f"{count(n)} {name}" for n, name in parts)
