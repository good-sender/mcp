#!/usr/bin/env python3
"""Print the tools a released GoodSender MCP binary advertises (MCP tools/list).

Usage:
  list_tools.py <path-to-goodsender-mcp-binary> <out.json>

The binary runs in local stdio mode. At startup it resolves the workspace for
its API key with GET <GOODSENDER_API_URL>/v1/mcp/session, so this script points
GOODSENDER_API_URL at a throwaway loopback mock that answers only that call.
Nothing reaches the real GoodSender API, and no real key or secret is used.

Action guards are disabled (GOODSENDER_DISABLE_ACTION_GUARDS=true) because the
hosted server, which the OpenAI plugin connects to, runs without them; with
guards on the local server would also list `confirm_action`.

Standard library only.
"""

import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading

PROTOCOL_VERSION = "2025-06-18"
TIMEOUT_SECONDS = 60


class _MockAPI(http.server.BaseHTTPRequestHandler):
    """Answers the startup session check; everything else is a 404."""

    def _reply(self):
        if self.path.split("?", 1)[0] == "/v1/mcp/session":
            status, body = 200, {"workspace_id": "ws_openai_plugin_listing"}
        else:
            status, body = 404, {"error": "not served by the listing mock"}
            sys.stderr.write(f"list_tools: mock API got unexpected {self.command} {self.path}\n")
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _reply

    def log_message(self, *args):
        pass


def _start_mock():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _MockAPI)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def list_tools(binary):
    mock = _start_mock()
    try:
        with tempfile.TemporaryDirectory() as data_dir:
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": data_dir,
                "GOODSENDER_API_URL": f"http://127.0.0.1:{mock.server_address[1]}",
                "GOODSENDER_API_KEY": "listing-only-not-a-real-key",
                "GOODSENDER_DATA_DIR": data_dir,
                "GOODSENDER_TELEMETRY": "false",
                "GOODSENDER_DISABLE_ACTION_GUARDS": "true",
            }
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "openai-plugin-package", "version": "0"},
                }},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            ]
            proc = subprocess.Popen(
                [binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env=env, text=True,
            )
            timer = threading.Timer(TIMEOUT_SECONDS, proc.kill)
            timer.start()
            try:
                responses = {}
                for request in requests:
                    proc.stdin.write(json.dumps(request) + "\n")
                    proc.stdin.flush()
                    if "id" not in request:
                        continue
                    while request["id"] not in responses:
                        line = proc.stdout.readline()
                        if not line:
                            raise SystemExit(
                                "list_tools: server exited early; stderr:\n" + proc.stderr.read()
                            )
                        message = json.loads(line)
                        if "id" in message:
                            responses[message["id"]] = message
            finally:
                timer.cancel()
                proc.kill()
                proc.wait()
    finally:
        mock.shutdown()

    init, listing = responses[1], responses[2]
    if "error" in listing:
        raise SystemExit(f"list_tools: tools/list failed: {listing['error']}")
    return {
        "serverInfo": init.get("result", {}).get("serverInfo", {}),
        "tools": listing["result"]["tools"],
    }


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: list_tools.py <goodsender-mcp-binary> <out.json>")
    result = list_tools(argv[1])
    if not result["tools"]:
        raise SystemExit("list_tools: the server listed no tools")
    with open(argv[2], "w", encoding="utf-8") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(f"list_tools: {len(result['tools'])} tools from "
          f"{result['serverInfo'].get('name', '?')} {result['serverInfo'].get('version', '?')}")


if __name__ == "__main__":
    main(sys.argv)
