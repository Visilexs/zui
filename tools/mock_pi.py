#!/usr/bin/env python3
"""A stand-in for `pi --mode rpc` that needs no model: it answers the RPC
commands pi-desk sends and plays a scripted agent run for each prompt
(thinking, a bash tool with streamed output, an edit, markdown text).
A prompt containing "dialog" asks an extension-UI select first.

    PI_DESK_PI="python3 tools/mock_pi.py" build/pi-desk
"""
import json
import os
import sys
import threading
import time

lock = threading.Lock()
aborted = threading.Event()
dialog_answer = {}
dialog_event = threading.Event()
state = {"model": {"provider": "mock", "id": "mock-1", "name": "Mock Model", "contextWindow": 200000},
         "thinking": "medium", "streaming": False, "name": None}
models = [state["model"], {"provider": "mock", "id": "mock-2", "name": "Mock Model Two", "contextWindow": 100000}]


def emit(record):
    with lock:
        sys.stdout.write(json.dumps(record) + "\n")
        sys.stdout.flush()


def respond(cmd, request_id, data=None, success=True, error=None):
    record = {"type": "response", "command": cmd, "success": success}
    if request_id is not None:
        record["id"] = request_id
    if data is not None:
        record["data"] = data
    if error:
        record["error"] = error
    emit(record)


def stream_text(index, kind, text, chunk=6, delay=0.012):
    emit({"type": "message_update", "assistantMessageEvent": {"type": kind + "_start", "contentIndex": index}})
    for i in range(0, len(text), chunk):
        if aborted.is_set():
            return False
        emit({"type": "message_update", "assistantMessageEvent": {"type": kind + "_delta", "contentIndex": index, "delta": text[i:i + chunk]}})
        time.sleep(delay)
    emit({"type": "message_update", "assistantMessageEvent": {"type": kind + "_end", "contentIndex": index, "content": text}})
    return True


THINKING = "The user wants a look at the project. I should list the files first, then fix the typo in the README, and summarise."
FINAL = """I looked around and fixed the README.

## What I found

- The project builds with **`./build.sh`** and has *three* modules
- `lib/ui.zeph` holds the layout engine
  - nested item with a [link](https://example.com)
1. numbered step one
2. numbered step two

> Note: nothing else needed changing.

```zephyr
fn main() {
    print("hello from zephyr")
}
```

| file | lines | status |
|------|------:|--------|
| ui.zeph | 1400 | ok |
| gfx.zeph | 420 | ok |

---

That's it — let me know if you want more."""


DEMO = """def greet(name):
    \"\"\"Say hello.\"\"\"
    print("hello " + name)


def main():
    for who in ["ada", "grace", "linus"]:
        greet(who)


if __name__ == "__main__":
    main()
"""


def stream_tool(index, call_id, name, args, chunk=7, delay=0.012):
    emit({"type": "message_update", "assistantMessageEvent": {"type": "toolcall_start", "contentIndex": index, "id": call_id, "toolName": name}})
    raw = json.dumps(args)
    out = 0
    for i in range(0, len(raw), chunk):
        out += 1
        emit({"type": "message_update", "usage": {"output": out * 2}, "assistantMessageEvent": {"type": "toolcall_delta", "contentIndex": index, "delta": raw[i:i + chunk]}})
        time.sleep(delay)
    call = {"type": "toolCall", "id": call_id, "name": name, "arguments": args}
    emit({"type": "message_update", "assistantMessageEvent": {"type": "toolcall_end", "contentIndex": index, "toolCall": call}})
    return call


def run_tool(call, apply):
    emit({"type": "tool_execution_start", "toolCallId": call["id"], "toolName": call["name"], "args": call["arguments"]})
    time.sleep(0.3)
    text = apply()
    result = {"content": [{"type": "text", "text": text}]}
    emit({"type": "tool_execution_end", "toolCallId": call["id"], "toolName": call["name"], "result": result, "isError": False})
    emit({"type": "message_end", "message": {"role": "toolResult", "toolCallId": call["id"], "toolName": call["name"], "content": result["content"], "isError": False}})


def run_file_demo():
    # a real write then a real edit in the current folder, both streamed
    path = os.path.join(os.getcwd(), "mock_demo.py")
    emit({"type": "message_start", "message": {"role": "assistant", "content": [], "stopReason": "pending"}})
    call = stream_tool(0, "call_w", "write", {"path": "mock_demo.py", "content": DEMO})
    emit({"type": "message_end", "message": {"role": "assistant", "content": [call], "stopReason": "toolUse"}})
    run_tool(call, lambda: open(path, "w").write(DEMO) and "Wrote mock_demo.py")
    if "pause" in os.environ.get("MOCK_FLAGS", ""):
        time.sleep(3)
    edits = [{"oldText": '    print("hello " + name)', "newText": '    greeting = f"hello, {name}!"\n    print(greeting.title())'},
             {"oldText": '["ada", "grace", "linus"]', "newText": '["ada", "grace", "linus", "margaret"]'}]
    emit({"type": "message_start", "message": {"role": "assistant", "content": [], "stopReason": "pending"}})
    call = stream_tool(0, "call_e", "edit", {"path": "mock_demo.py", "edits": edits}, chunk=3, delay=0.03)
    emit({"type": "message_end", "message": {"role": "assistant", "content": [call], "stopReason": "toolUse"}})
    def apply():
        text = open(path).read()
        for e in edits:
            text = text.replace(e["oldText"], e["newText"], 1)
        open(path, "w").write(text)
        return "Applied 2 edits to mock_demo.py"
    run_tool(call, apply)


ZEPHYR_SAMPLE = """Here is a Zephyr sample (labeled, then unlabeled):

```zephyr
import "std/math.zeph"

/* block comments /* nest */ too */
const MAX_ITEMS = 0xFF_FF
enum Shape { Circle, Square }

struct Point { x: float = 0.0, y: float = 1.5e-3 }

impl Point {
    fn len(self) -> float { return sqrt(self.x * self.x + self.y * self.y) }
}

fn describe(p: Point, names: [str: int]) -> str? {
    let tab = '\\t'
    var total = 0
    for i in 0..names.len() { total += i }
    if total > MAX_ITEMS and not names.has("x") { return none }
    defer print("done")
    let path = r"C:\\dir\\{raw}"
    return "point ({p.x}, {p.y}) has length {p.len()}\\n"
}
```

```
fn main() {
    let words = "a b c".split(" ")
    print("{words.len()} words")
}
```
"""

def run(prompt, images=()):
    aborted.clear()
    state["streaming"] = True
    emit({"type": "agent_start"})
    emit({"type": "turn_start"})
    content = [{"type": "text", "text": prompt}] + list(images) if images else prompt
    user = {"role": "user", "content": content, "timestamp": 0}
    emit({"type": "message_start", "message": user})
    emit({"type": "message_end", "message": user})
    if "dialog" in prompt:
        emit({"type": "extension_ui_request", "id": "ui-1", "method": "select", "title": "Allow dangerous command?", "options": ["Allow", "Block"]})
        dialog_event.wait(30)
        dialog_event.clear()
        emit({"type": "extension_ui_request", "id": "ui-2", "method": "notify", "message": "You chose: " + str(dialog_answer.get("value", dialog_answer)), "notifyType": "info"})
    if "zephyr sample" in prompt:
        emit({"type": "message_start", "message": {"role": "assistant", "content": [], "stopReason": "pending"}})
        stream_text(0, "text", ZEPHYR_SAMPLE)
        emit({"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": ZEPHYR_SAMPLE}], "stopReason": "stop"}})
        emit({"type": "agent_end", "messages": [], "willRetry": False})
        state["streaming"] = False
        emit({"type": "agent_settled"})
        return
    if "file" in prompt:
        run_file_demo()
        emit({"type": "agent_end", "messages": [], "willRetry": False})
        state["streaming"] = False
        emit({"type": "agent_settled"})
        return
    emit({"type": "message_start", "message": {"role": "assistant", "content": [], "stopReason": "pending"}})
    ok = stream_text(0, "thinking", THINKING) and stream_text(1, "text", "Let me look at the files first.")
    call = {"type": "toolCall", "id": "call_1", "name": "bash", "arguments": {"command": "ls -la && wc -l lib/*.zeph"}}
    if ok:
        emit({"type": "message_update", "assistantMessageEvent": {"type": "toolcall_start", "contentIndex": 2, "id": "call_1", "toolName": "bash"}})
        emit({"type": "message_update", "assistantMessageEvent": {"type": "toolcall_end", "contentIndex": 2, "toolCall": call}})
    content = [{"type": "thinking", "thinking": THINKING}, {"type": "text", "text": "Let me look at the files first."}, call]
    emit({"type": "message_end", "message": {"role": "assistant", "content": content, "stopReason": "aborted" if not ok else "toolUse"}})
    if ok:
        emit({"type": "tool_execution_start", "toolCallId": "call_1", "toolName": "bash", "args": call["arguments"]})
        output = ""
        for line in ["total 24", "drwxr-xr-x  app", "drwxr-xr-x  lib", "-rwxr-xr-x  build.sh", "  1400 lib/ui.zeph", "   420 lib/gfx.zeph", "  1820 total"]:
            if aborted.is_set():
                ok = False
                break
            output += line + "\n"
            emit({"type": "tool_execution_update", "toolCallId": "call_1", "toolName": "bash", "args": call["arguments"], "partialResult": {"content": [{"type": "text", "text": output}]}})
            time.sleep(0.15)
        result = {"content": [{"type": "text", "text": output}]}
        emit({"type": "tool_execution_end", "toolCallId": "call_1", "toolName": "bash", "result": result, "isError": False})
        emit({"type": "message_start", "message": {"role": "toolResult", "toolCallId": "call_1", "toolName": "bash", "content": result["content"], "isError": False}})
        emit({"type": "message_end", "message": {"role": "toolResult", "toolCallId": "call_1", "toolName": "bash", "content": result["content"], "isError": False}})
    if ok:
        edit = {"type": "toolCall", "id": "call_2", "name": "edit", "arguments": {"path": "/home/user/project/README.md", "edits": [{"oldText": "Teh project", "newText": "The project"}]}}
        emit({"type": "message_start", "message": {"role": "assistant", "content": [], "stopReason": "pending"}})
        emit({"type": "message_update", "assistantMessageEvent": {"type": "toolcall_start", "contentIndex": 0, "id": "call_2", "toolName": "edit"}})
        emit({"type": "message_update", "assistantMessageEvent": {"type": "toolcall_end", "contentIndex": 0, "toolCall": edit}})
        emit({"type": "message_end", "message": {"role": "assistant", "content": [edit], "stopReason": "toolUse"}})
        emit({"type": "tool_execution_start", "toolCallId": "call_2", "toolName": "edit", "args": edit["arguments"]})
        time.sleep(0.2)
        result = {"content": [{"type": "text", "text": "Applied 1 edit to README.md"}]}
        emit({"type": "tool_execution_end", "toolCallId": "call_2", "toolName": "edit", "result": result, "isError": False})
        emit({"type": "message_start", "message": {"role": "assistant", "content": [], "stopReason": "pending"}})
        ok = stream_text(0, "text", FINAL, chunk=9, delay=0.01)
        emit({"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": FINAL}], "stopReason": "stop" if ok else "aborted"}})
    emit({"type": "agent_end", "messages": [], "willRetry": False})
    state["streaming"] = False
    emit({"type": "agent_settled"})


def main():
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            cmd = json.loads(raw)
        except ValueError:
            respond("parse", None, success=False, error="bad json")
            continue
        kind = cmd.get("type")
        rid = cmd.get("id")
        if kind == "get_state":
            data = {"model": state["model"], "thinkingLevel": state["thinking"], "isStreaming": state["streaming"],
                    "isCompacting": False, "sessionFile": "", "sessionId": "mock", "messageCount": 0, "pendingMessageCount": 0}
            if state["name"]:
                data["sessionName"] = state["name"]
            respond(kind, rid, data)
        elif kind == "get_available_models":
            respond(kind, rid, {"models": models})
        elif kind == "get_available_thinking_levels":
            respond(kind, rid, {"levels": ["off", "minimal", "low", "medium", "high"]})
        elif kind == "get_messages":
            respond(kind, rid, {"messages": []})
        elif kind == "get_session_stats":
            respond(kind, rid, {"tokens": {"total": 12345}, "cost": 0.0123, "contextUsage": {"tokens": 24000, "contextWindow": 200000, "percent": 12}})
        elif kind == "set_model":
            for m in models:
                if m["id"] == cmd.get("modelId"):
                    state["model"] = m
            respond(kind, rid, state["model"])
        elif kind == "set_thinking_level":
            state["thinking"] = cmd.get("level")
            respond(kind, rid)
            emit({"type": "thinking_level_changed", "level": state["thinking"]})
        elif kind in ("new_session", "switch_session"):
            respond(kind, rid, {"cancelled": False})
        elif kind == "abort":
            aborted.set()
            respond(kind, rid)
        elif kind == "extension_ui_response":
            dialog_answer.clear()
            dialog_answer.update(cmd)
            dialog_event.set()
        elif kind == "get_commands":
            respond(kind, rid, {"commands": [
                {"name": "fix-tests", "description": "Fix failing tests", "source": "prompt"},
                {"name": "skill:frontend-design", "description": "Distinctive frontend design", "source": "skill"},
                {"name": "deploy", "description": "Deploy the current branch", "source": "extension"}]})
        elif kind == "bash":
            def run_bash(rid=rid, command=cmd.get("command")):
                out = ""
                for i in range(4):
                    chunk = "line %d of %s\n" % (i + 1, command)
                    out += chunk
                    emit({"type": "bash_execution_update", "id": rid, "delta": chunk})
                    time.sleep(0.1)
                respond("bash", rid, {"output": out, "exitCode": 0, "cancelled": False, "truncated": False})
            threading.Thread(target=run_bash, daemon=True).start()
        elif kind == "cycle_model":
            i = models.index(state["model"]) if state["model"] in models else 0
            state["model"] = models[(i + 1) % len(models)]
            respond(kind, rid, {"model": state["model"], "thinkingLevel": state["thinking"], "isScoped": False})
        elif kind == "cycle_thinking_level":
            levels = ["off", "minimal", "low", "medium", "high"]
            state["thinking"] = levels[(levels.index(state["thinking"]) + 1) % len(levels)]
            respond(kind, rid, {"level": state["thinking"]})
        elif kind == "clear_queue":
            respond(kind, rid, {"steering": ["queued steer text"], "followUp": []})
        elif kind == "get_fork_messages":
            respond(kind, rid, {"messages": [{"entryId": "e1", "text": "Please look at the project"}]})
        elif kind == "fork":
            respond(kind, rid, {"text": "Please look at the project", "cancelled": False})
        elif kind == "get_tree":
            respond(kind, rid, {"tree": [{"entry": {"type": "message", "id": "e1", "message": {"role": "user", "content": "Please look at the project"}},
                "children": [{"entry": {"type": "message", "id": "e2", "message": {"role": "assistant", "content": [{"type": "text", "text": "Sure, looking now."}]}}, "children": []},
                             {"entry": {"type": "message", "id": "e3", "message": {"role": "assistant", "content": [{"type": "text", "text": "An alternative branch."}]}}, "children": []}]}], "leafId": "e2"})
        elif kind == "export_html":
            respond(kind, rid, {"path": cmd.get("outputPath", "/tmp/mock-session.html")})
        elif kind == "set_session_name":
            state["name"] = cmd.get("name")
            respond(kind, rid)
            emit({"type": "session_info_changed", "name": state["name"]})
        elif kind == "compact":
            emit({"type": "compaction_start", "reason": "manual"})
            time.sleep(0.2)
            emit({"type": "compaction_end", "reason": "manual", "result": {"tokensBefore": 24000, "estimatedTokensAfter": 6000}, "aborted": False, "willRetry": False})
            respond(kind, rid, {"tokensBefore": 24000, "estimatedTokensAfter": 6000})
        elif kind == "prompt":
            if state["streaming"]:
                respond(kind, rid, {"disposition": "queued"})
                emit({"type": "queue_update", "steering": [cmd.get("message")], "followUp": []})
            else:
                respond(kind, rid, {"disposition": "started"})
                threading.Thread(target=run, args=(cmd.get("message", ""), cmd.get("images") or []), daemon=True).start()
        else:
            respond(kind, rid)


if __name__ == "__main__":
    main()
