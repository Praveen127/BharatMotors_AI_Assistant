"""
mcp/client.py
Client for mcp/server.py. Spawns the server as a subprocess and speaks
JSON-RPC 2.0 over its stdin/stdout, exactly as a real MCP client would
against an MCP server started with a stdio transport.

Usage:
    with MCPClient() as client:
        tools = client.list_tools()
        result = client.call_tool("check_warranty_status", {"vehicle_reg": "MH12AB1234"})
"""
import sys
import os
import json
import subprocess
import itertools

SERVER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")


class MCPClient:
    def __init__(self):
        self._proc = None
        self._id_counter = itertools.count(1)

    def __enter__(self):
        self._proc = subprocess.Popen(
            [sys.executable, SERVER_PATH],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._proc:
            self._proc.stdin.close()
            self._proc.terminate()
            self._proc.wait(timeout=5)

    def _call(self, method: str, params: dict = None) -> dict:
        req = {"jsonrpc": "2.0", "id": next(self._id_counter), "method": method,
               "params": params or {}}
        self._proc.stdin.write(json.dumps(req) + "\n")
        self._proc.stdin.flush()
        line = self._proc.stdout.readline()
        return json.loads(line)

    def list_tools(self):
        resp = self._call("tools/list")
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict):
        resp = self._call("tools/call", {"name": name, "arguments": arguments})
        if "error" in resp:
            raise RuntimeError(resp["error"]["message"])
        return resp["result"]


if __name__ == "__main__":
    with MCPClient() as client:
        print("Available MCP tools:")
        for t in client.list_tools():
            print(f"  - {t['name']}: {t['description'][:70]}...")
        print("\nSample call: check_warranty_status(MH12AB1234)")
        print(client.call_tool("check_warranty_status", {"vehicle_reg": "MH12AB1234"}))
