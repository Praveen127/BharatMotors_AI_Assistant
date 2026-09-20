"""
planner.py
Phase 6: lightweight multi-step task decomposition. Many real customer
messages bundle more than one request in a single turn (e.g. "Is my car
still under warranty AND can you find me a service center for a brake
noise?"). The planner splits these into ordered sub-tasks so the agent can
retrieve/act on each one and combine the results, instead of only
addressing the first clause.
"""
import re
from dataclasses import dataclass
from typing import List

SPLIT_RE = re.compile(r"\band also\b|\balso,?\b|\?\s+(?=[A-Z])|\band\b(?=.*\?)", re.I)


@dataclass
class SubTask:
    text: str


def decompose(user_message: str) -> List[SubTask]:
    """Splits a compound message into sub-tasks. Falls back to a single
    task if no clear split point is found (avoids over-splitting simple
    sentences that merely contain the word 'and')."""
    # Only attempt decomposition if there's a real signal of two asks:
    # two question marks, or an explicit "also"/"and also".
    two_questions = user_message.count("?") >= 2
    has_also = bool(re.search(r"\balso\b", user_message, re.I))

    if not (two_questions or has_also):
        return [SubTask(text=user_message.strip())]

    parts = re.split(r"(?<=[?.])\s+(?:and also|also|and)\s+", user_message, flags=re.I)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        parts = [p.strip() for p in re.split(r"\?", user_message) if p.strip()]
        parts = [p + "?" for p in parts]
    return [SubTask(text=p) for p in parts] if parts else [SubTask(text=user_message.strip())]
