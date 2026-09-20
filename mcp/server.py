"""
mcp/server.py
Exposes the agent's tools (tools/tool_registry.py) as an MCP server built
on `fastmcp` (https://github.com/jlowin/fastmcp) -- the standard
high-level Python framework for writing MCP servers, used here instead of
hand-rolled JSON-RPC. Each tool is registered with a single `@mcp.tool()`
decorator; fastmcp derives the tool's JSON schema from the Python type
hints and docstring automatically.

Run standalone (stdio transport, the MCP default):
    python -m mcp.server
    # or: fastmcp run mcp/server.py

Connect an MCP-compatible client (Claude Desktop, an IDE, another agent
framework, etc.) by pointing it at this file/command -- no code here needs
to change for that; that interoperability is the point of building on MCP
rather than a bespoke tool-calling format.

OFFLINE FALLBACK: this sandbox has no network access to `pip install
fastmcp`, so if the import fails, this module transparently falls back to
`mcp/_stdio_fallback_server.py` -- a hand-rolled JSON-RPC-over-stdio server
speaking the same `tools/list` / `tools/call` method contract fastmcp's
stdio transport uses, so `mcp/client.py` works unmodified either way. This
is the same offline-first pattern used for the LLM and embedding backends
(see docs/engineering_justification.md §3) -- install `fastmcp` and this
file uses it automatically, with zero code changes.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

try:
    from fastmcp import FastMCP
    _HAS_FASTMCP = True
except ImportError:
    _HAS_FASTMCP = False

from tools import tool_registry


if _HAS_FASTMCP:
    mcp = FastMCP(
        name="Bharat Motors Support Tools",
        instructions=("Tools for Bharat Motors customer support: warranty "
                       "lookup, service-center locator, recall check, and "
                       "human escalation ticket creation."),
    )

    @mcp.tool()
    def check_warranty_status(vehicle_reg: str) -> dict:
        """Look up the warranty status of a vehicle by its registration
        number (e.g. 'MH12AB1234'). Use this before answering any
        warranty-coverage question that requires the customer's specific
        vehicle record."""
        return tool_registry.check_warranty_status(vehicle_reg)

    @mcp.tool()
    def locate_service_center(pincode: str) -> dict:
        """Find the nearest authorized Bharat Motors service centers for a
        given 6-digit PIN code."""
        return tool_registry.locate_service_center(pincode)

    @mcp.tool()
    def check_recall_status(vin: str) -> dict:
        """Check whether a specific VIN (17-character Vehicle
        Identification Number) has an active safety recall campaign.
        Always use this instead of guessing recall status."""
        return tool_registry.check_recall_status(vin)

    @mcp.tool()
    def create_escalation_ticket(issue_summary: str, severity: str = "MEDIUM",
                                  category: str = "general") -> dict:
        """Create a ticket to escalate a case to a human specialist. Use
        for safety-critical, legal, recall, repeated-complaint, or
        refund/discount requests, or any request that cannot be answered
        confidently from verified sources. `severity` is one of
        CRITICAL/HIGH/MEDIUM."""
        return tool_registry.create_escalation_ticket(issue_summary, severity, category)

    def serve_forever():
        # fastmcp defaults to the stdio transport, matching the MCP spec's
        # standard local-server transport (the same one Claude Desktop and
        # most MCP clients use to launch a local tool server).
        mcp.run()

else:
    # No fastmcp installed -- delegate entirely to the offline fallback,
    # which implements the same tool set over the same stdio wire shape.
    from mcp._stdio_fallback_server import serve_forever as _fallback_serve_forever

    def serve_forever():
        print("[mcp/server] fastmcp not installed -- using offline JSON-RPC "
              "fallback (mcp/_stdio_fallback_server.py). `pip install "
              "fastmcp` to use the real implementation.", file=sys.stderr)
        _fallback_serve_forever()


if __name__ == "__main__":
    serve_forever()
