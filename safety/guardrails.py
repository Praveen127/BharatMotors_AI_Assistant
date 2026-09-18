"""
guardrails.py
Implements the four Scenario 3 safety requirements as explicit, testable
checks that run BEFORE the LLM generates a response (not just prompt-level
instructions). This keeps safety enforceable and auditable independent of
LLM prompt-following reliability.

  1. Refuse unsafe or policy-violating requests.
  2. Must not fabricate policies          -> enforced in retriever.py (grounding).
  3. Must escalate sensitive/unresolved cases.
  4. Must not store personal data in logs -> enforced in pii_filter.py.
"""
import re
from dataclasses import dataclass
from enum import Enum


class GuardrailVerdict(Enum):
    ALLOW = "allow"
    REFUSE = "refuse"
    ESCALATE_CRITICAL = "escalate_critical"
    ESCALATE_HIGH = "escalate_high"
    ESCALATE_MEDIUM = "escalate_medium"


@dataclass
class GuardrailResult:
    verdict: GuardrailVerdict
    reason: str
    message: str = ""


# --- 1. Hard refusals: unsafe / policy-violating requests -------------------
REFUSAL_PATTERNS = [
    (r"\bfalsify|fake\b.*\b(service record|odometer|accident report)\b",
     "falsifying records"),
    (r"\bbypass|skip|ignore\b.*\brecall\b", "bypassing a safety recall"),
    (r"\b(another|other|someone else'?s?)\s+customer.*(detail|info|record|data)s?\b",
     "requesting another customer's personal data"),
    (r"\blegal advice\b|\bsue\b", "legal/liability advice"),
    (r"\bguarantee\b.*\b(warranty|claim)\b.*\bapprov", "guaranteeing a claim outcome"),
    (r"\bdiscount code\b|\bwaive (the )?(fee|charge)\b.*\bwithout\b", "unauthorized discount/waiver"),
]

# --- 3. Mandatory escalation triggers ---------------------------------------
CRITICAL_PATTERNS = [
    r"\bsmoke\b", r"\bfire\b", r"\bburning\b", r"\bfuel (leak|smell)\b",
    r"\bbrakes?\b.*\b(fail|failed|failing|not work(ing)?|stopped work)\b",
    r"\bsteering\b.*\b(fail|failed|failing|locked|not (working|responding))\b",
    r"\bairbag\b.*\b(deployed|malfunction)\b",
    r"\baccident\b.*\binjur",
]
HIGH_PATTERNS = [
    r"\brecall\b", r"\binsurance claim\b", r"\baccident\b(?!.*injur)", r"\blegal",
    r"\bwho'?s? (is )?at fault\b", r"\bfault\b.*\baccident\b",
]
MEDIUM_PATTERNS = [
    r"\brefund\b", r"\bdiscount\b", r"\bwaive\b", r"\bunhappy\b|\bfrustrat|\bangry\b|\bterrible service\b",
    r"\b(second|third|again)\s+time\b", r"\balready (told|reported|said)\b",
    r"\bstill not (fixed|working|resolved)\b", r"\bnothing (has been|was) done\b",
]


def _matches_any(text: str, patterns) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)


def evaluate(user_message: str, repeated_complaint: bool = False) -> GuardrailResult:
    """Run all guardrail checks on a raw user message and return the first
    applicable verdict, in priority order: refuse > critical > high > medium
    > allow."""
    for pattern, reason in REFUSAL_PATTERNS:
        if re.search(pattern, user_message, re.I):
            return GuardrailResult(
                verdict=GuardrailVerdict.REFUSE,
                reason=reason,
                message=("I'm not able to help with that request "
                          f"({reason}), as it goes against Bharat Motors "
                          "policy. I can escalate this to a human specialist "
                          "if you'd like, or help with something else."),
            )

    if _matches_any(user_message, CRITICAL_PATTERNS):
        return GuardrailResult(
            verdict=GuardrailVerdict.ESCALATE_CRITICAL,
            reason="safety-critical vehicle symptom",
            message=("This sounds like it could be a safety issue. If there "
                      "is any immediate danger, please stop using the "
                      "vehicle and contact roadside assistance or emergency "
                      "services now. I'm escalating this to a specialist "
                      "immediately."),
        )

    if repeated_complaint or _matches_any(user_message, HIGH_PATTERNS):
        return GuardrailResult(
            verdict=GuardrailVerdict.ESCALATE_HIGH,
            reason="recall/legal/repeated-complaint case",
            message=("I want to make sure this is handled properly, so I'm "
                      "escalating it to a specialist who can look into it in "
                      "detail."),
        )

    if _matches_any(user_message, MEDIUM_PATTERNS):
        return GuardrailResult(
            verdict=GuardrailVerdict.ESCALATE_MEDIUM,
            reason="refund/discount/dissatisfaction request",
            message=("I've noted this and I'm creating a ticket for our "
                      "team to review, since this isn't something I can "
                      "resolve directly."),
        )

    return GuardrailResult(verdict=GuardrailVerdict.ALLOW, reason="no trigger matched")
