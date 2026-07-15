#!/usr/bin/env python3
"""ops_probe.py — non-interactive ops-agent loop (ai-01).

Asks the local LLM (via LiteLLM) an ops question and lets it drive the
READ-ONLY fleet-mcp tools to an answer. Two jobs:
  - the ops-agent liveness verification check (canned question, bounded turns)
  - scripted "why is X down?" diagnosis runs
Interactive / human-in-the-loop usage goes through ollmcp instead
(ops/ops-agent.sh) — this probe is safe headless because every fleet tool
is read-only by construction.

Usage:
  /opt/llm/fleet-venv/bin/python ops_probe.py "why is foo.service down on the rig?"
Env: LITELLM_API_KEY (or --api-key), OPS_MODEL (default coder), OPS_BASE.
"""
import argparse
import asyncio
import json
import os
import sys
import urllib.request

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

SYSTEM = """You are the homelab ops agent. You have READ-ONLY inspection tools
for the fleet (rig, mini, nas). Investigate the user's question with the tools
— check service status, journals, containers, URLs — then give a concise
diagnosis: the ROOT CAUSE first, then the evidence. Do not guess: if a tool
answers it, cite it. When you have the answer, reply WITHOUT calling more tools."""


def chat(base, key, model, messages, tools):
    body = {"model": model, "messages": messages, "tools": tools,
            "temperature": 0.1, "max_tokens": 4096}
    req = urllib.request.Request(base + "/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


async def run(args):
    async with streamablehttp_client(args.mcp_url) as (read, write, _):
        async with ClientSession(read, write) as sess:
            await sess.initialize()
            tools = (await sess.list_tools()).tools
            oai_tools = [{"type": "function",
                          "function": {"name": t.name,
                                       "description": t.description or "",
                                       "parameters": t.inputSchema}} for t in tools]
            messages = [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": args.question}]
            for _ in range(args.max_turns):
                resp = chat(args.base, args.api_key, args.model, messages, oai_tools)
                msg = resp["choices"][0]["message"]
                tcs = msg.get("tool_calls") or []
                messages.append({"role": "assistant",
                                 "content": msg.get("content") or "",
                                 **({"tool_calls": tcs} if tcs else {})})
                if not tcs:
                    print(msg.get("content") or "(empty)")
                    return 0
                for tc in tcs:
                    name = tc["function"]["name"]
                    try:
                        targs = json.loads(tc["function"]["arguments"] or "{}")
                        res = await sess.call_tool(name, targs)
                        text = "\n".join(c.text for c in res.content
                                         if getattr(c, "text", None))
                    except Exception as e:
                        text = f"TOOL ERROR: {type(e).__name__}: {e}"
                    if not args.quiet:
                        print(f"[tool] {name}({tc['function']['arguments'][:120]})",
                              file=sys.stderr)
                    messages.append({"role": "tool", "tool_call_id": tc.get("id", "x"),
                                     "content": text[:8000]})
            print("ERROR: turn budget exhausted without a final answer")
            return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--model", default=os.environ.get("OPS_MODEL", "coder"))
    ap.add_argument("--base", default=os.environ.get("OPS_BASE", "http://localhost:4000/v1"))
    ap.add_argument("--api-key", default=os.environ.get("LITELLM_API_KEY", "none"))
    ap.add_argument("--mcp-url", default="http://localhost:8765/mcp")
    ap.add_argument("--max-turns", type=int, default=8)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
