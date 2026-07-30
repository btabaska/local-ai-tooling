#!/usr/bin/env python3
"""prefix-cache-probe.py — does llama.cpp prefix caching actually work on our model?

WHY THIS EXISTS (read before interpreting results)
--------------------------------------------------
Prefix caching is THE enabling mechanism for an agent swarm: N agents share one
long system prompt + AGENTS.md + repo map, so only the first should pay for
prefill. Published traces of real coding-agent sessions put ~96% of prompt tokens
on the prefix-cache path.

But our `coder` (Qwen3.6-35B-A3B) is a HYBRID linear-attention model — only 10 of
its 40 layers hold a real KV cache. That is exactly why 262k context fits in
23.3 GB (10,240 B/token at q8_0, 4x cheaper than a conventional 30B)... and
llama.cpp issue #24055 reports that context checkpoints are ALWAYS INVALIDATED on
hybrid/recurrent models, with the log line:

    "forcing full prompt re-processing due to lack of cache data
     (likely due to SWA or hybrid/recurrent memory"

Same architectural property, opposite consequences. If checkpoints are broken
here, the swarm plan needs a different model — which changes every VRAM number in
the plan. This probe settles it in ~5 minutes.

EXPERIMENTAL DESIGN
-------------------
Naive "send it twice and see if it's faster" proves nothing — the second run could
be faster from variance, or from a response cache. So we run three measured
requests against a deterministic ~12k-token prompt:

    WARMUP  short prompt          -> loads the model, excluded from results
    P1      prefix A (cold)       -> baseline: what a real prefill costs
    P2      prefix A again        -> the test: should skip prefill if caching works
    P3      prefix B (cold)       -> CONTROL: a fresh prefix, proves P2 was not
                                     just "the machine got faster"

Each request shares its long prefix and differs only in a short trailing nonce,
which is precisely the swarm case (same system prompt, different task) and also
defeats any whole-response caching.

We measure TIME TO FIRST TOKEN via streaming. TTFT is dominated by prefill, so a
cache hit shows up as a large TTFT drop. Generation is capped at a few tokens so
decode speed does not pollute the signal.

INTERPRETATION
--------------
    P2 << P1 and P3 ~= P1   -> CACHING WORKS. Proceed with the swarm plan.
    P1 ~= P2 ~= P3          -> CACHING BROKEN (issue #24055 reproduces).
                               Do NOT build the swarm on this model as-is.

Usage:
    ./prefix-cache-probe.py                          # defaults: coder on llama-swap
    ./prefix-cache-probe.py --model qwen3.6-27b      # test coder-strong instead
    ./prefix-cache-probe.py --tokens 24000           # bigger prefix, louder signal
    ./prefix-cache-probe.py --check-logs             # also grep the container logs
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE = os.environ.get("PROBE_BASE", "http://localhost:9292/v1")
DEFAULT_MODEL = os.environ.get("PROBE_MODEL", "qwen3.6-35b-a3b")
API_KEY = os.environ.get("PROBE_KEY", "none")
WARNING_NEEDLE = "forcing full prompt re-processing"

# A deterministic word pool. Real-ish prose tokenizes closer to real prompts than
# repeated filler would, and a fixed seed keeps runs comparable across hosts.
_WORDS = (
    "service handler request context module interface buffer pointer thread channel "
    "registry adapter payload schema migration rollback checksum manifest quota latency "
    "throughput cursor iterator predicate scheduler dispatcher allocator namespace "
    "transaction invariant boundary contract fixture assertion regression telemetry"
).split()


def build_prompt(approx_tokens: int, seed: int) -> str:
    """Deterministic pseudo-prose of roughly `approx_tokens` tokens."""
    state = seed * 6364136223846793005 + 1442695040888963407
    out, count = [], 0
    # ~1 token per word for common English; pad to be safe rather than sorry.
    while count < approx_tokens:
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        out.append(_WORDS[(state >> 33) % len(_WORDS)])
        count += 1
        if count % 12 == 0:
            out.append("\n")
    return " ".join(out)


def ttft(base, model, api_key, prompt, nonce, max_tokens=4, timeout=900):
    """Stream one completion; return (time_to_first_token, total_time, usage|None).

    The nonce is appended AFTER the shared prefix so the cacheable region is
    identical between runs.
    """
    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": f"{prompt}\n\n[request-id {nonce}] Reply with the single word: ok"}
        ],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    t0 = time.time()
    first = None
    usage = None
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            if chunk.get("usage"):
                usage = chunk["usage"]
            choices = chunk.get("choices") or []
            if first is None and choices:
                delta = choices[0].get("delta") or {}
                # Count the first chunk carrying ANY generated payload. Reasoning
                # models may emit reasoning_content before content.
                if delta.get("content") or delta.get("reasoning_content"):
                    first = time.time() - t0
    return first, time.time() - t0, usage


def container_logs(since="10m", container="llama-swap"):
    try:
        out = subprocess.run(
            ["docker", "logs", "--since", since, container],
            capture_output=True, text=True, timeout=30,
        )
        return (out.stdout or "") + (out.stderr or "")
    except Exception as exc:  # docker absent, wrong host, no perms
        return f"<could not read logs: {exc}>"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=DEFAULT_BASE, help=f"OpenAI-compatible base URL (default {DEFAULT_BASE})")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"model id (default {DEFAULT_MODEL})")
    ap.add_argument("--key", default=API_KEY)
    ap.add_argument("--tokens", type=int, default=12000, help="approx shared-prefix size in tokens (default 12000)")
    ap.add_argument("--check-logs", action="store_true", help="also grep container logs for the #24055 warning")
    ap.add_argument("--container", default="llama-swap")
    args = ap.parse_args()

    prefix_a = build_prompt(args.tokens, seed=1)
    prefix_b = build_prompt(args.tokens, seed=2)

    print(f"probe: base={args.base} model={args.model} prefix≈{args.tokens} tokens")
    print("NOTE: hit llama-swap DIRECTLY, not the LiteLLM gateway — a response cache")
    print("      or prompt rewriting in the gateway would invalidate this measurement.\n")

    try:
        print("[warmup] loading model (excluded from results) …", flush=True)
        _, warm_total, _ = ttft(args.base, args.model, args.key, "Reply with: ok", "warmup", max_tokens=2)
        print(f"[warmup] done in {warm_total:.1f}s\n")

        results = {}
        for label, prefix, desc in (
            ("P1", prefix_a, "prefix A, cold      (baseline: real prefill cost)"),
            ("P2", prefix_a, "prefix A AGAIN      (the test: should be cached)"),
            ("P3", prefix_b, "prefix B, cold      (control: proves P2 wasn't luck)"),
        ):
            print(f"[{label}] {desc} …", flush=True)
            first, total, usage = ttft(args.base, args.model, args.key, prefix, f"{label}-{time.time():.0f}")
            results[label] = first if first is not None else total
            pt = (usage or {}).get("prompt_tokens")
            print(f"[{label}] TTFT={results[label]:.2f}s  total={total:.2f}s"
                  + (f"  prompt_tokens={pt}" if pt else "") + "\n")
    except urllib.error.URLError as exc:
        print(f"\nERROR: could not reach {args.base} — {exc}", file=sys.stderr)
        print("Is llama-swap up?  docker compose ps llama-swap", file=sys.stderr)
        return 2

    p1, p2, p3 = results["P1"], results["P2"], results["P3"]
    speedup = p1 / p2 if p2 > 0 else float("inf")
    control = p3 / p1 if p1 > 0 else 0

    print("=" * 68)
    print(f"  P1 cold      {p1:6.2f}s")
    print(f"  P2 cached?   {p2:6.2f}s     speedup vs P1: {speedup:5.2f}x")
    print(f"  P3 control   {p3:6.2f}s     ratio to P1:    {control:5.2f}x")
    print("=" * 68)

    # A real prefix-cache hit skips nearly all prefill. Require both a large P2
    # speedup AND a control that stayed slow, so we cannot be fooled by variance.
    cached = speedup >= 2.0 and control >= 0.6
    if cached:
        print("\nVERDICT: PREFIX CACHING WORKS ✅")
        print("  P2 skipped prefill while the fresh prefix P3 still paid for it.")
        print("  -> The swarm plan holds. Proceed with tier 3 (serving profiles,")
        print("     --cache-ram, --cache-reuse, slot save/restore around GPU yields).")
    elif speedup >= 2.0 and control < 0.6:
        print("\nVERDICT: INCONCLUSIVE ⚠️")
        print("  P2 was fast, but so was the fresh prefix P3 — so the speedup is")
        print("  probably warmup/variance, not caching. Re-run with --tokens 24000.")
    else:
        print("\nVERDICT: PREFIX CACHING IS NOT WORKING ❌")
        print("  Re-running an identical prefix cost about the same as a cold one.")
        print("  This is consistent with llama.cpp #24055 on hybrid/recurrent models.")
        print("  -> Do NOT build the swarm on this model as-is. Options:")
        print("     (a) find/build a llama.cpp revision with both the #24055 fix and")
        print("         the GBNF tool-call fix (>=9755 / 2026-06-21);")
        print("     (b) accept ~1/128 malformed tool calls on an older build (b9309)")
        print("         that reportedly still checkpoints correctly;")
        print("     (c) move `coder` to a non-hybrid model — costs 4x the KV cache,")
        print("         which invalidates every context ceiling in the plan.")

    if args.check_logs:
        print(f"\n--- scanning `docker logs {args.container}` for the #24055 warning ---")
        logs = container_logs(container=args.container)
        hits = [ln for ln in logs.splitlines() if WARNING_NEEDLE in ln]
        if hits:
            print(f"FOUND {len(hits)} occurrence(s) — this is direct confirmation:")
            for ln in hits[-5:]:
                print("  " + ln.strip())
        else:
            print(f"no '{WARNING_NEEDLE}' lines found "
                  "(good sign, but absence is weaker evidence than the timings above)")

    return 0 if cached else 1


if __name__ == "__main__":
    sys.exit(main())
