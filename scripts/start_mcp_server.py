"""
scripts/start_mcp_server.py
Starts mcp/server.py as a standalone stdio JSON-RPC process. Intended to be
run as a long-lived process that an MCP-compatible client (e.g. mcp/client.py,
or any external MCP client) can attach to. See mcp/client.py for a working
example client, and logs/mcp_events.log for the call audit trail.

Run:  python scripts/start_mcp_server.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from mcp.server import serve_forever

if __name__ == "__main__":
    print("Starting Bharat Motors MCP tool server (stdio transport). "
          "Waiting for JSON-RPC requests on stdin...", file=sys.stderr)
    serve_forever()
