"""
mcp/client.py
Client for mcp/server.py, built on `fastmcp.Client`. fastmcp's client is
async (MCP's stdio transport is asyncio-based under the hood), so calls go
through `asyncio.run(...)`; `MCPClient` below wraps that in a small sync
facade so the rest of this project (which is otherwise synchronous) can
call it the same way it called the previous hand-rolled version.

Usage:
    with MCPClient() as client:
        tools = client.list_tools()
        result = client.call_tool("check_warranty_status",
                                    {"vehicle_reg": "MH12AB1234"})

OFFLINE FALLBACK: if `fastmcp` is not installed, this transparently uses
`mcp/_stdio_fallback_client.py` instead, which speaks the same tool-call
interface against `mcp/_stdio_fallback_server.py`. See mcp/server.py's
docstring and docs/engineering_justification.md §3.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

SERVER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")

try:
    from fastmcp import Client as _FastMCPClient
    _HAS_FASTMCP = True
except ImportError:
    _HAS_FASTMCP = False


if _HAS_FASTMCP:
    class MCPClient:
        """Sync wrapper around fastmcp.Client, spawning mcp/server.py as a
        stdio subprocess (fastmcp infers the stdio transport from a .py
        script path)."""

        def __init__(self):
            self._client = _FastMCPClient(SERVER_SCRIPT)
            self._loop = None

        def __enter__(self):
            self._loop = asyncio.new_event_loop()
            self._loop.run_until_complete(self._client.__aenter__())
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self._loop.run_until_complete(self._client.__aexit__(exc_type, exc_val, exc_tb))
            self._loop.close()

        def list_tools(self):
            tools = self._loop.run_until_complete(self._client.list_tools())
            return [{"name": t.name, "description": t.description} for t in tools]

        def call_tool(self, name: str, arguments: dict):
            result = self._loop.run_until_complete(self._client.call_tool(name, arguments))
            # fastmcp wraps the return value in a CallToolResult; .data holds
            # the tool's actual Python return value (a dict, here).
            return result.data if hasattr(result, "data") else result

else:
    from mcp._stdio_fallback_client import MCPClient  # noqa: F401


if __name__ == "__main__":
    with MCPClient() as client:
        print(f"MCP backend: {'fastmcp' if _HAS_FASTMCP else 'offline JSON-RPC fallback'}")
        print("Available MCP tools:")
        for t in client.list_tools():
            print(f"  - {t['name']}: {t['description'][:70]}...")
        print("\nSample call: check_warranty_status(MH12AB1234)")
        print(client.call_tool("check_warranty_status", {"vehicle_reg": "MH12AB1234"}))
