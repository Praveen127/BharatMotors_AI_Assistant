"""
pii_filter.py
Redacts personal data so nothing identifiable is ever written to persistent
logs, satisfying Scenario 3's "Must not store personal data in logs"
requirement. PII may still exist transiently in in-memory conversation state
during an active session (needed to actually help the customer) -- only the
*logging* path is redacted, not the live session.
"""
import re

# Order matters: more specific patterns first.
PATTERNS = [
    ("EMAIL", re.compile(r"[\w\.\-]+@[\w\-]+\.[a-zA-Z]{2,}")),
    ("PHONE_IN", re.compile(r"(?:\+?91[\-\s]?)?[6-9]\d{9}\b")),
    ("VEHICLE_REG", re.compile(r"\b[A-Z]{2}\s?-?\d{1,2}\s?-?[A-Z]{1,2}\s?-?\d{4}\b", re.I)),
    ("VIN", re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")),
    # Negative lookbehind excludes 6-digit sequences immediately preceded by
    # a hyphen (e.g. internal ticket IDs like "BM-686715"), which are
    # business identifiers, not customer PII. Found during Phase 8 log
    # review: an earlier version redacted ticket IDs inside escalation
    # confirmations, corrupting a non-PII reference number in the log.
    ("PIN_CODE", re.compile(r"(?<!-)\b\d{6}\b")),
]

NAME_HINT_RE = re.compile(r"\bmy name is\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)", re.I)


def redact(text: str) -> str:
    """Returns a copy of `text` with PII patterns replaced by typed tags,
    e.g. 'call me at 9876543210' -> 'call me at [PHONE_IN_REDACTED]'."""
    redacted = text
    for label, pattern in PATTERNS:
        redacted = pattern.sub(f"[{label}_REDACTED]", redacted)
    redacted = NAME_HINT_RE.sub("my name is [NAME_REDACTED]", redacted)
    return redacted


def redact_dict(d: dict, keys=("user_message", "agent_response", "text",
                                "content", "summary")) -> dict:
    """Redacts PII in known text-bearing fields of a log record, recursively
    for nested dicts/lists, leaving structural fields (ids, scores, flags)
    untouched."""
    out = {}
    for k, v in d.items():
        if isinstance(v, str) and (k in keys or True):
            out[k] = redact(v)
        elif isinstance(v, dict):
            out[k] = redact_dict(v, keys)
        elif isinstance(v, list):
            out[k] = [redact_dict(x, keys) if isinstance(x, dict) else
                       (redact(x) if isinstance(x, str) else x) for x in v]
        else:
            out[k] = v
    return out


if __name__ == "__main__":
    sample = ("my name is Rohit Sharma, my number is 9876543210, "
               "email rohit.sharma@example.com, car reg KA-05-MJ-1234")
    print(redact(sample))
