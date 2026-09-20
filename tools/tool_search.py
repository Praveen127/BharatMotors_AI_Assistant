"""
tool_search.py
Routing/selection logic (Phase 5): decides which registered tool, if any, a
user message requires, and extracts the argument from the message using
simple entity patterns. This is the "tool selection" layer that sits in
front of tool execution -- in the real LangChain path this role is played by
the agent's function-calling/ReAct loop; this module provides an explicit,
testable/offline version of the same decision plus loop-prevention guardrails.
"""
import re
from dataclasses import dataclass
from typing import Optional

VEHICLE_REG_RE = re.compile(r"\b[A-Z]{2}\s?-?\d{1,2}\s?-?[A-Z]{1,2}\s?-?\d{4}\b", re.I)
VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
PINCODE_RE = re.compile(r"\b\d{6}\b")

MAX_TOOL_CALLS_PER_TURN = 3  # loop-prevention safeguard


@dataclass
class ToolCallPlan:
    tool_name: Optional[str]
    args: dict
    confidence: str  # "high" | "low" | "none"
    note: str = ""


def route(user_message: str) -> ToolCallPlan:
    msg = user_message.lower()

    reg_match = VEHICLE_REG_RE.search(user_message)
    vin_match = VIN_RE.search(user_message)
    pin_match = PINCODE_RE.search(user_message)

    if "warranty" in msg or "covered" in msg:
        if reg_match:
            return ToolCallPlan("check_warranty_status", {"vehicle_reg": reg_match.group(0)}, "high")
        return ToolCallPlan("check_warranty_status", {}, "low",
                             note="warranty intent detected but no registration number found in message")

    if "recall" in msg:
        if vin_match:
            return ToolCallPlan("check_recall_status", {"vin": vin_match.group(0)}, "high")
        return ToolCallPlan("check_recall_status", {}, "low",
                             note="recall intent detected but no VIN found in message")

    if any(kw in msg for kw in ["service center", "service centre", "nearest service",
                                  "workshop near"]):
        if pin_match:
            return ToolCallPlan("locate_service_center", {"pincode": pin_match.group(0)}, "high")
        return ToolCallPlan("locate_service_center", {}, "low",
                             note="service-center intent detected but no PIN code found")

    return ToolCallPlan(None, {}, "none", note="no tool intent detected")
