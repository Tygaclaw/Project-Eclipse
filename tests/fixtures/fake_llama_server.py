#!/usr/bin/env python3
"""Test double for a llama.cpp server used by runtime integration tests.

It speaks the real OpenAI-compatible HTTP/SSE contract and accepts the same
launch flags ECLIPSE passes to llama-server. It is test infrastructure only and
is never imported by the product.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONTEXT = 4096
MODEL_NAME = "fake-model"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args: object) -> None:  # silence request logging
        return

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        elif self.path == "/props":
            self._json(
                200,
                {
                    "default_generation_settings": {"n_ctx": CONTEXT},
                    "model_path": MODEL_NAME,
                },
            )
        elif self.path == "/v1/models":
            self._json(200, {"data": [{"id": MODEL_NAME}]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if self.path != "/v1/chat/completions":
            self._json(404, {"error": "not found"})
            return
        messages = payload.get("messages") or []
        last_user = next(
            (item.get("content", "") for item in reversed(messages) if item.get("role") == "user"),
            "",
        )
        saw_tool_result = any(item.get("role") == "tool" for item in messages)
        use_tool = "TOOL" in last_user.upper() and not saw_tool_result

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        def sse(obj: dict) -> None:
            self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode())
            self.wfile.flush()
            time.sleep(0.01)

        if use_tool:
            sse(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {"name": "write_file", "arguments": ""},
                                    }
                                ]
                            }
                        }
                    ]
                }
            )
            sse(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {
                                            "arguments": '{"path": "created_by_agent.txt", "content": "hello"}'
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            )
            sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]})
        else:
            for piece in ("Hello", " from the", " fake server."):
                sse({"choices": [{"delta": {"content": piece}}]})
            sse(
                {
                    "choices": [{"delta": {}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 7, "completion_tokens": 5, "total_tokens": 12},
                }
            )
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def main() -> int:
    global CONTEXT, MODEL_NAME
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ctx-size", type=int, default=4096)
    parser.add_argument("-m", "--model", default=MODEL_NAME)
    parser.add_argument("--n-gpu-layers", default="0")
    parser.add_argument("--parallel", default="1")
    parser.add_argument("--threads", default="1")
    parser.add_argument("--jinja", action="store_true")
    parser.add_argument("--cache-type-k", default="f16")
    parser.add_argument("--cache-type-v", default="f16")
    parser.add_argument("extra", nargs="*")
    args = parser.parse_args()

    CONTEXT = args.ctx_size
    MODEL_NAME = args.model
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
