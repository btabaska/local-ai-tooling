#!/usr/bin/env python3
"""Agentic tool-calling bake-off harness (ai-01).

Drives an OpenAI-compatible endpoint through a REAL repo loop
(inspect -> multi-file edit -> run tests -> fix) using function calling,
and scores TOOL-CALL FIDELITY + task success — not chat quality.

Each run copies a task fixture into a temp sandbox; the model gets
list_files / read_file / write_file / run_tests. Success = unittest
suite passes AND the model stops cleanly.

Usage:
  python3 harness.py --model qwen3-coder-30b --task bugfix
  python3 harness.py --all            # every model x task, serial
Results appended as JSONL to results/results.jsonl
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, time, urllib.request, urllib.error

BASE = os.environ.get("BAKEOFF_BASE", "http://localhost:9292/v1")
API_KEY = os.environ.get("BAKEOFF_KEY", "none")
MODELS = ["qwen3.6-27b", "qwen3.6-35b-a3b", "qwen3-coder-30b", "devstral-24b"]
TASKS = ["bugfix", "feature"]
MAX_TURNS = 20
HERE = os.path.dirname(os.path.abspath(__file__))

TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List all files in the project.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file and return its full content.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relative path"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Create or fully overwrite a file with new content.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "run_tests", "description": "Run the project's unittest suite and return the output.", "parameters": {"type": "object", "properties": {}, "required": []}}},
]

SYSTEM = """You are a coding agent working in a small Python project.
Make the project's tests pass. Rules:
- NEVER edit test files (test_*.py); fix or add source code instead.
- Use the tools to inspect files, edit code, and run the tests.
- After editing, always run the tests again to check.
- When all tests pass, reply with the single word DONE and no tool call."""


def call_llm(model, messages):
    # Sampler: default to OMITTING temperature so llama-swap's per-model
    # HF-card values apply (coder/coder-strong: --temp 0.6 --top-p 0.95
    # --top-k 20 --min-p 0). The previous hardcoded 0.1 silently overrode
    # them, so the 2026-07-15 bake-off was NOT measured at the sampler the
    # stack actually serves. Set BAKEOFF_TEMP/BAKEOFF_TOP_P to sweep.
    body = {"model": model, "messages": messages, "tools": TOOLS,
            "max_tokens": 4096}
    if os.environ.get("BAKEOFF_TEMP"):
        body["temperature"] = float(os.environ["BAKEOFF_TEMP"])
    if os.environ.get("BAKEOFF_TOP_P"):
        body["top_p"] = float(os.environ["BAKEOFF_TOP_P"])
    req = urllib.request.Request(BASE + "/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + API_KEY})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r), time.time() - t0


def safe_path(sandbox, path):
    full = os.path.realpath(os.path.join(sandbox, path))
    if not full.startswith(os.path.realpath(sandbox) + os.sep):
        raise ValueError("path escapes sandbox")
    return full


def run_tests(sandbox):
    p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", ".", "-v"],
                       cwd=sandbox, capture_output=True, text=True, timeout=120)
    out = (p.stdout + p.stderr)[-4000:]
    return p.returncode == 0, out


def exec_tool(sandbox, name, args, stats):
    if name == "list_files":
        fs = []
        for root, dirs, files in os.walk(sandbox):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                fs.append(os.path.relpath(os.path.join(root, f), sandbox))
        return "\n".join(sorted(fs))
    if name == "read_file":
        with open(safe_path(sandbox, args["path"])) as f:
            return f.read()
    if name == "write_file":
        rel = args["path"]
        if os.path.basename(rel).startswith("test_"):
            stats["test_edit_attempts"] += 1
            return "ERROR: editing test files is forbidden"
        full = safe_path(sandbox, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True) if os.path.dirname(full) else None
        with open(full, "w") as f:
            f.write(args["content"])
        return f"wrote {len(args['content'])} bytes to {rel}"
    if name == "run_tests":
        ok, out = run_tests(sandbox)
        stats["last_tests_ok"] = ok
        return out
    raise KeyError(name)


def run_one(model, task):
    fixture = os.path.join(HERE, "tasks", task)
    sandbox = tempfile.mkdtemp(prefix=f"bakeoff-{model.replace('.', '_')}-")
    shutil.copytree(fixture, sandbox, dirs_exist_ok=True)
    with open(os.path.join(fixture, "PROMPT.txt")) as f:
        prompt = f.read().strip()

    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt}]
    stats = {"model": model, "task": task, "turns": 0, "malformed_calls": 0,
             "tool_calls": 0, "test_edit_attempts": 0, "last_tests_ok": False,
             "completion_tokens": 0, "prompt_tokens": 0, "gen_seconds": 0.0,
             "success": False, "outcome": "max_turns", "wall_seconds": 0.0}
    t_start = time.time()
    try:
        for turn in range(MAX_TURNS):
            stats["turns"] = turn + 1
            try:
                resp, dt = call_llm(model, messages)
            except urllib.error.HTTPError as e:
                detail = e.read()[:300].decode(errors="replace")
                # 400s on tool responses usually mean the model emitted a
                # malformed call the server-side parser rejected earlier
                stats["malformed_calls"] += 1
                stats["outcome"] = f"http_{e.code}: {detail}"
                break
            usage = resp.get("usage", {})
            stats["completion_tokens"] += usage.get("completion_tokens", 0)
            stats["prompt_tokens"] = max(stats["prompt_tokens"], usage.get("prompt_tokens", 0))
            stats["gen_seconds"] += dt
            msg = resp["choices"][0]["message"]
            tool_calls = msg.get("tool_calls") or []
            messages.append({"role": "assistant",
                             "content": msg.get("content") or "",
                             **({"tool_calls": tool_calls} if tool_calls else {})})
            if not tool_calls:
                content = (msg.get("content") or "").strip()
                ok, _ = run_tests(sandbox)
                stats["last_tests_ok"] = ok
                if "DONE" in content.upper():
                    stats["success"] = ok
                    stats["outcome"] = "done" if ok else "hallucinated_done"
                else:
                    stats["outcome"] = "stopped_without_done"
                    stats["success"] = ok
                break
            for tc in tool_calls:
                stats["tool_calls"] += 1
                name = tc.get("function", {}).get("name", "")
                raw = tc.get("function", {}).get("arguments", "")
                try:
                    args = json.loads(raw) if raw else {}
                    if not isinstance(args, dict):
                        raise ValueError("args not an object")
                    result = exec_tool(sandbox, name, args, stats)
                except (json.JSONDecodeError, KeyError, ValueError, TypeError, OSError) as e:
                    stats["malformed_calls"] += 1
                    result = f"TOOL ERROR: {type(e).__name__}: {e}"
                messages.append({"role": "tool", "tool_call_id": tc.get("id", "x"),
                                 "content": str(result)[:8000]})
            if stats["last_tests_ok"]:
                # tests green: give the model one turn to notice and stop
                pass
    finally:
        stats["wall_seconds"] = round(time.time() - t_start, 1)
        stats["tok_per_sec"] = round(stats["completion_tokens"] / stats["gen_seconds"], 1) if stats["gen_seconds"] else 0
        shutil.rmtree(sandbox, ignore_errors=True)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--task")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    runs = [(m, t) for m in MODELS for t in TASKS] if args.all else [(args.model, args.task)]
    out_path = os.path.join(HERE, "results", "results.jsonl")
    for model, task in runs:
        print(f"=== {model} / {task} ===", flush=True)
        stats = run_one(model, task)
        print(json.dumps(stats), flush=True)
        with open(out_path, "a") as f:
            f.write(json.dumps(stats) + "\n")


if __name__ == "__main__":
    main()
