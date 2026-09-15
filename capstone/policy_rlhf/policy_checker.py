"""
policy_checker.py
Post-generation compliance check: after the agent produces a response, this
checks it against data/policy/policy.json rules (forbidden over-promising
phrases, escalation-response must include a ticket ID, safety-critical
responses must tell the customer to stop using the vehicle, etc). This is a
second, independent safety net alongside the pre-generation guardrails in
safety/guardrails.py -- guardrails decide WHETHER to let the LLM answer;
policy_checker verifies WHAT the LLM actually said before it reaches the
customer.
"""
import json
import os
from dataclasses import dataclass
from typing import List

POLICY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "data", "policy", "policy.json")


def load_policy() -> dict:
    with open(POLICY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class PolicyCheckResult:
    passed: bool
    violations: List[str]


def check_response(response_text: str, is_escalation: bool = False,
                    is_safety_critical: bool = False) -> PolicyCheckResult:
    policy = load_policy()
    violations = []
    lower = response_text.lower()

    for phrase in policy["response_rules"]["forbidden_phrases"]:
        if phrase in lower:
            violations.append(f"forbidden_phrase:'{phrase}'")

    if is_escalation:
        if "ticket" not in lower:
            violations.append("missing_required_field:ticket_id")

    if is_safety_critical:
        needed = policy["response_rules"]["required_on_safety_critical"]
        if not any(term in lower for term in needed):
            violations.append("missing_safety_language")

    return PolicyCheckResult(passed=(len(violations) == 0), violations=violations)
