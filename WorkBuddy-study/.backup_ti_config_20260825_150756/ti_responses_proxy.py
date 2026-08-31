#!/usr/bin/env python3
# Codex <-> 腾讯云 TI 协议转换代理
# ----------------------------------------------------------------------------
# 为什么需要它（设计决策）：
#   - Codex 2026.2 起只支持 wire_api="responses"（OpenAI Responses API），
#     wire_api="chat" 已被移除，无法直连 /v1/chat/completions。
#   - 但 TI 的 /v1/responses 不支持 tools（实测 500），而底层的
#     /v1/chat/completions 完整支持 function calling。
#   - 故本代理：Codex --Responses--> 代理 --Chat Completions(非流式, 嵌套tools)--> TI
#                TI tool_calls --翻回--> Responses function_call --SSE--> Codex
#   - 代理【始终以非流式】与 TI 通信：规避 TI chat/completions 流式格式与
#     标准 OpenAI SSE 不兼容、以及偶发 TLS 中断的问题；拿到完整 JSON 后自行
#     封装成标准 Responses SSE 事件流返回给 Codex。
# 运行：TI_API_KEY=xxx python ti_responses_proxy.py  (监听 127.0.0.1:8787)
# ----------------------------------------------------------------------------
import json, os, uuid, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

TI_BASE = "https://ms-gdc6t9h5-100043467125-sw.gw.ap-shanghai.ti.tencentcs.com/ms-gdc6t9h5/v1"
TI_KEY = os.environ.get("TI_API_KEY", "")
LISTEN = ("127.0.0.1", 8787)


def convert_request(body):
    """Responses 请求 -> Chat Completions 请求（始终非流式）"""
    out = {"model": body.get("model") or "ms-gdc6t9h5", "messages": [], "stream": False}
    if body.get("instructions"):
        out["messages"].append({"role": "system", "content": body["instructions"]})
    messages = out["messages"]
    pending_tool_calls = []

    def flush_pending():
        if pending_tool_calls:
            messages.append({"role": "assistant", "content": None, "tool_calls": list(pending_tool_calls)})
            pending_tool_calls.clear()

    inp = body.get("input")
    if isinstance(inp, str):
        messages.append({"role": "user", "content": inp})
    elif isinstance(inp, list):
        for item in inp:
            t = item.get("type")
            if t == "message":
                if item.get("role") == "assistant" and pending_tool_calls:
                    flush_pending()
                messages.append({"role": item.get("role"), "content": item.get("content")})
            elif t == "function_call":
                pending_tool_calls.append({
                    "id": item.get("call_id") or ("call_" + uuid.uuid4().hex[:12]),
                    "type": "function",
                    "function": {"name": item.get("name"), "arguments": item.get("arguments") or ""},
                })
            elif t == "function_call_output":
                flush_pending()
                messages.append({"role": "tool", "tool_call_id": item.get("call_id"), "content": item.get("output")})
    flush_pending()

    tools = body.get("tools")
    if tools:
        out["tools"] = [{
            "type": "function",
            "function": {"name": t.get("name"), "description": t.get("description", ""), "parameters": t.get("parameters", {})},
        } for t in tools if t.get("type") == "function"]

    if isinstance(body.get("reasoning"), dict) and body["reasoning"].get("effort"):
        out["reasoning_effort"] = body["reasoning"]["effort"]
    return out


def build_response_object(model, output_items, usage=None, status="completed"):
    return {
        "id": "resp_" + uuid.uuid4().hex[:24],
        "object": "response",
        "created_at": int(time.time()),
        "model": model,
        "output": output_items,
        "status": status,
        "usage": usage or {"prompt_tokens": 0, "total_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0},
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "error": None,
        "incomplete_details": None,
        "instructions": None,
        "max_output_tokens": None,
        "previous_response_id": None,
        "reasoning": {"effort": None, "summary": None},
        "store": True,
        "temperature": None,
        "text": {"format": {"type": "text"}},
        "top_p": None,
        "truncation": "disabled",
        "user": None,
        "metadata": {},
    }


def build_output_from_chat(data):
    """Chat Completions 响应 -> Responses output 列表 + usage"""
    choice = data["choices"][0]["message"]
    output = []
    usage = data.get("usage", {})
    if choice.get("tool_calls"):
        for tc in choice["tool_calls"]:
            output.append({
                "type": "function_call",
                "name": tc["function"]["name"],
                "arguments": tc["function"]["arguments"],
                "call_id": tc.get("id") or ("call_" + uuid.uuid4().hex[:12]),
                "status": "completed",
            })
    else:
        output.append({
            "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": choice.get("content") or "", "annotations": [], "logprobs": None}],
        })
    u = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "reasoning_tokens": usage.get("reasoning_tokens", 0),
    }
    return output, u


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.rstrip("/") != "/v1/responses":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception as e:
            self.send_error(400, str(e))
            return

        want_sse = bool(body.get("stream", False))  # Codex 想要流式？我们仍用非流式与 TI 通信
        chat_req = convert_request(body)
        payload = json.dumps(chat_req).encode()
        req = urllib.request.Request(TI_BASE + "/chat/completions", data=payload, method="POST")
        req.add_header("Authorization", "Bearer " + TI_KEY)
        req.add_header("Content-Type", "application/json")

        last_err = None
        resp = None
        for _ in range(3):  # TI 网关 TLS 偶发中断，重试 3 次
            try:
                resp = urllib.request.urlopen(req, timeout=180)
                break
            except urllib.error.HTTPError as e:
                err = e.read().decode(errors="replace")
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(err.encode())
                return
            except Exception as e:
                last_err = e
                time.sleep(1)
        if resp is None:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "upstream failed: %s" % last_err}).encode())
            return
        try:
            data = json.loads(resp.read().decode())
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "bad upstream json: %s" % e}).encode())
            return

        output, usage = build_output_from_chat(data)
        if want_sse:
            self.emit_sse(chat_req["model"], output, usage)
        else:
            robj = build_response_object(chat_req["model"], output, usage)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(robj).encode())

    def emit_sse(self, model, output, usage):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        w = self.wfile
        seq = [0]
        r0 = build_response_object(model, [], status="in_progress")

        def ev(event_type, obj):
            obj["type"] = event_type
            obj["sequence_number"] = seq[0]
            seq[0] += 1
            w.write(("event: " + event_type + "\n").encode())
            w.write(("data: " + json.dumps(obj) + "\n\n").encode())
            w.flush()

        ev("response.created", {"response": r0})
        ev("response.in_progress", {"response": r0})

        if output and output[0]["type"] == "function_call":
            item = dict(output[0])
            item["id"] = item.get("call_id")
            ev("response.output_item.added", {"response": r0, "item": item})
            ev("response.output_item.done", {"response": r0, "item": item})
        else:
            msg = output[0] if output else {
                "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": "", "annotations": []}],
            }
            item_id = "msg_" + uuid.uuid4().hex[:24]
            added = dict(msg)
            added["id"] = item_id
            ev("response.output_item.added", {"response": r0, "item": added})
            text = ""
            if msg.get("content") and msg["content"][0].get("text") is not None:
                text = msg["content"][0]["text"]
            ev("response.output_text.delta", {"response": r0, "item_id": item_id, "content_index": 0, "delta": text})
            ev("response.output_text.done", {"response": r0, "item_id": item_id, "content_index": 0, "text": text})
            ev("response.output_item.done", {"response": r0, "item": added})

        rdone = build_response_object(model, output, usage)
        ev("response.completed", {"response": rdone})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("[proxy] listening", LISTEN, "TI_KEY set:", bool(TI_KEY), flush=True)
    HTTPServer(LISTEN, Handler).serve_forever()
