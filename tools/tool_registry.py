"""
tool_registry.py
Defines the tools available to the agent and exposes them both as plain
Python callables (used by the offline/mock execution path) and as LangChain
`Tool` objects (used by the real langchain.agents.AgentExecutor path in
agent/core_agent.py when langchain is installed).

Mock data stores (WARRANTY_DB, SERVICE_CENTERS) simulate backend systems a
real deployment would call via internal APIs.
"""
import random
import string
from typing import Dict, List

# ---- Mock backend data ------------------------------------------------
WARRANTY_DB = {
    "MH12AB1234": {"model": "Bharat Cruze Mid", "purchase_date": "2025-03-14",
                    "odometer_km": 18500, "warranty_km_limit": 40000,
                    "warranty_months": 24, "status": "ACTIVE",
                    "extended_warranty": False},
    "KA05MJ1234": {"model": "Bharat Trailblaze Explorer", "purchase_date": "2023-01-05",
                    "odometer_km": 52000, "warranty_km_limit": 40000,
                    "warranty_months": 24, "status": "EXPIRED",
                    "extended_warranty": False},
    "DL8CAF5678": {"model": "Bharat Volt Long Range", "purchase_date": "2024-11-20",
                    "odometer_km": 9000, "warranty_km_limit": 40000,
                    "warranty_months": 24, "status": "ACTIVE",
                    "extended_warranty": True},
}

SERVICE_CENTERS = {
    "560001": [{"name": "Bharat Motors Service — MG Road", "distance_km": 2.1,
                 "phone": "080-XXXX-1001"},
                {"name": "Bharat Motors Service — Indiranagar", "distance_km": 5.4,
                 "phone": "080-XXXX-1002"}],
    "110001": [{"name": "Bharat Motors Service — Connaught Place", "distance_km": 1.8,
                 "phone": "011-XXXX-2001"}],
    "400001": [{"name": "Bharat Motors Service — Fort", "distance_km": 3.0,
                 "phone": "022-XXXX-3001"}],
}

RECALLS_DB = {
    # VIN prefix -> active recall info
    "MA3ERLF1S00123456": {"campaign": "RC-2026-014", "issue": "Fuel pump wiring harness",
                            "severity": "HIGH"},
}

_TICKETS: List[dict] = []


def check_warranty_status(vehicle_reg: str) -> Dict:
    """Look up warranty status for a vehicle registration number."""
    key = vehicle_reg.upper().replace("-", "").replace(" ", "")
    record = WARRANTY_DB.get(key)
    if not record:
        return {"found": False, "message": "No warranty record found for that registration number."}
    return {"found": True, **record}


def locate_service_center(pincode: str) -> Dict:
    """Return nearest authorized service centers for a PIN code."""
    centers = SERVICE_CENTERS.get(pincode.strip())
    if not centers:
        return {"found": False, "message": f"No service centers indexed for PIN {pincode}. "
                                             "Please provide the city name instead."}
    return {"found": True, "centers": centers}


def check_recall_status(vin: str) -> Dict:
    """Look up whether a VIN has an active safety recall."""
    record = RECALLS_DB.get(vin.upper())
    if not record:
        return {"found": False, "active_recall": False,
                 "message": "No active recall found for this VIN."}
    return {"found": True, "active_recall": True, **record}


def create_escalation_ticket(issue_summary: str, severity: str = "MEDIUM",
                              category: str = "general") -> Dict:
    """Create a human-escalation ticket. Returns a ticket ID and SLA."""
    ticket_id = "BM-" + "".join(random.choices(string.digits, k=6))
    sla_map = {"CRITICAL": "within minutes (on-call specialist)",
               "HIGH": "within 4 business hours", "MEDIUM": "within 1 business day"}
    ticket = {
        "ticket_id": ticket_id,
        "issue_summary": issue_summary,
        "severity": severity,
        "category": category,
        "sla": sla_map.get(severity, "within 1 business day"),
        "status": "OPEN",
    }
    _TICKETS.append(ticket)
    return ticket


def get_all_tickets() -> List[dict]:
    return list(_TICKETS)


# ---- Tool schema (for LangChain Tool / function-calling registration) -----
TOOL_SPECS = [
    {
        "name": "check_warranty_status",
        "description": ("Look up the warranty status of a vehicle by its "
                         "registration number (e.g. 'MH12AB1234'). Use this "
                         "before answering any warranty-coverage question "
                         "that requires the customer's specific vehicle "
                         "record."),
        "func": check_warranty_status,
        "args": {"vehicle_reg": "string, vehicle registration number"},
    },
    {
        "name": "locate_service_center",
        "description": ("Find the nearest authorized Bharat Motors service "
                         "centers for a given 6-digit PIN code."),
        "func": locate_service_center,
        "args": {"pincode": "string, 6-digit PIN code"},
    },
    {
        "name": "check_recall_status",
        "description": ("Check whether a specific VIN (17-character Vehicle "
                         "Identification Number) has an active safety "
                         "recall campaign. Always use this instead of "
                         "guessing recall status."),
        "func": check_recall_status,
        "args": {"vin": "string, 17-character VIN"},
    },
    {
        "name": "create_escalation_ticket",
        "description": ("Create a ticket to escalate a case to a human "
                         "specialist. Use for safety-critical, legal, "
                         "recall, repeated-complaint, or refund/discount "
                         "requests, or any request the agent cannot answer "
                         "confidently from verified sources."),
        "func": create_escalation_ticket,
        "args": {"issue_summary": "string", "severity": "one of CRITICAL/HIGH/MEDIUM",
                  "category": "string"},
    },
]


def get_langchain_tools():
    """Wraps TOOL_SPECS as langchain.tools.Tool objects. Only imports
    langchain lazily so this module still works in offline/mock mode where
    langchain may not be installed."""
    from langchain.tools import Tool
    tools = []
    for spec in TOOL_SPECS:
        tools.append(Tool(name=spec["name"], description=spec["description"],
                            func=spec["func"]))
    return tools
