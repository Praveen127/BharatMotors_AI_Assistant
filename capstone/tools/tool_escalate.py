"""
tool_escalate.py
Thin, dedicated wrapper around tool_registry.create_escalation_ticket used by
the safety layer and the planner, so escalation is a first-class, explicitly
named action distinct from ordinary information-lookup tools.
"""
from tools.tool_registry import create_escalation_ticket, get_all_tickets
from safety.guardrails import GuardrailVerdict

_SEVERITY_MAP = {
    GuardrailVerdict.ESCALATE_CRITICAL: "CRITICAL",
    GuardrailVerdict.ESCALATE_HIGH: "HIGH",
    GuardrailVerdict.ESCALATE_MEDIUM: "MEDIUM",
}


def escalate_from_guardrail(guardrail_result, user_message: str) -> dict:
    """Creates a ticket from a GuardrailResult, mapping its verdict to the
    correct severity/category and using a redacted issue summary."""
    from safety.pii_filter import redact
    severity = _SEVERITY_MAP.get(guardrail_result.verdict, "MEDIUM")
    ticket = create_escalation_ticket(
        issue_summary=redact(user_message),
        severity=severity,
        category=guardrail_result.reason,
    )
    return ticket


def list_open_tickets():
    return [t for t in get_all_tickets() if t["status"] == "OPEN"]
