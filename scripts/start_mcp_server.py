"""
scripts/start_mcp_server.py
Starts mcp/server.py as a standalone MCP server process (fastmcp, stdio
transport -- or the offline JSON-RPC fallback if fastmcp isn't installed;
see mcp/server.py's docstring). Intended to be run as a long-lived process
that an MCP-compatible client (mcp/client.py, Claude Desktop, or any other
MCP client) can attach to. logs/mcp_events.log has the fallback path's call
audit trail (fastmcp's own logging, when active, goes to stderr).

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
