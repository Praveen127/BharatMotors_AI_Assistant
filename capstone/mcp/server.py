"""
mcp/server.py
A minimal Model Context Protocol (MCP) style server: JSON-RPC 2.0 messages
over stdio, exposing the agent's tools (tools/tool_registry.py) as
remotely-callable MCP tools. This mirrors the real transport MCP servers use
(newline-delimited JSON-RPC over stdin/stdout), implemented directly with
the standard library so it runs without the `mcp` SDK or network access
(see README "Offline Mode"). Swapping this for `mcp.server.fastmcp` in a
networked environment is a drop-in change — the JSON-RPC method contract
(`tools/list`, `tools/call`) is the same shape the official SDK uses.

Run standalone:  python -m mcp.server
(reads JSON-RPC requests from stdin, one per line, writes responses to stdout)
"""
import sys
import json
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from tools import tool_registry

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "mcp_events.log")


def _log_event(event: dict):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    event = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def handle_request(req: dict) -> dict:
    method = req.get("method")
    req_id = req.get("id")

    if method == "tools/list":
        tools = [{"name": t["name"], "description": t["description"], "args": t["args"]}
                  for t in tool_registry.TOOL_SPECS]
        _log_event({"method": method, "id": req_id, "result_count": len(tools)})
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

    if method == "tools/call":
        params = req.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})
        spec = next((t for t in tool_registry.TOOL_SPECS if t["name"] == name), None)
        if spec is None:
            _log_event({"method": method, "id": req_id, "tool": name, "status": "unknown_tool"})
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {name}"}}
        try:
            result = spec["func"](**args)
            _log_event({"method": method, "id": req_id, "tool": name,
                        "args_keys": list(args.keys()), "status": "ok"})
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as e:
            _log_event({"method": method, "id": req_id, "tool": name, "status": "error",
                        "error": str(e)})
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32000, "message": str(e)}}

    _log_event({"method": method, "id": req_id, "status": "unknown_method"})
    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def serve_forever():
    _log_event({"event": "server_start"})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle_request(req)
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    serve_forever()
