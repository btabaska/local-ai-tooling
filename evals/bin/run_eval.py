#!/usr/bin/env python3
"""Eval runner: drive opencode headless per task card, capture full trajectories.

Usage:
  python3 run_eval.py --cards <cards.jsonl> --model litellm/coder --out <results-dir> \
      [--agent plan] [--only id1,id2] [--timeout 420]

Per card: runs `opencode run --format json` in an empty per-attempt workdir (closed-book),
saves raw event stream + parsed attempt.json. Read-only by construction: the plan agent
denies bash/edit; the only reachable tools are read-only MCPs (fleet-mcp etc.).
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import time

PREAMBLE = (
    "You are the operations assistant for Brandon's homelab "
    "(hosts: mini = Ubuntu docker host running ~38 containers in /opt/stacks, "
    "nas = Synology DS920+ with the *arr stack/Plex/Immich/Calibre-Web, "
    "rig = CachyOS box with a 3090 Ti running the AI stack and game servers, "
    "seedbox = remote Deluge-only download box, ha = Home Assistant). "
    "Answer the question below concretely and completely. Where commands are relevant, "
    "show the exact commands. Do not execute anything that mutates any host.\n\n---\n\n"
)


def load_cards(path, only=None):
    cards = [json.loads(l) for l in open(path) if l.strip()]
    if only:
        keep = set(x.strip() for x in only.split(","))
        missing = keep - {c["id"] for c in cards}
        if missing:
            raise SystemExit(f"unknown card ids: {sorted(missing)}")
        cards = [c for c in cards if c["id"] in keep]
    return cards


def parse_events(raw_lines):
    """Tolerant parse of the --format json event stream (plugins print non-JSON noise)."""
    events, noise = [], []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            noise.append(line)
    return events, noise


def extract(events):
    """Pull final text + tool calls out of the event stream, tolerating format variants.

    opencode emits message *part* events; text parts stream cumulative snapshots keyed by
    part id (last snapshot per id wins), tool parts carry state {status,input,output}.
    """
    text_parts = {}   # part_id -> latest text
    tool_parts = {}   # part_id -> latest tool state
    order = []
    for e in events:
        part = None
        # nested part first: the OUTER event type mirrors the part type ("text" etc.),
        # but the payload lives in e["part"] — checking e first extracts nothing
        for candidate in (e.get("part"), (e.get("properties") or {}).get("part"), e):
            if isinstance(candidate, dict) and candidate.get("type") in ("text", "tool", "reasoning"):
                part = candidate
                break
        if not part:
            continue
        pid = part.get("id") or f"anon-{len(order)}"
        if pid not in text_parts and pid not in tool_parts:
            order.append(pid)
        if part.get("type") == "text" and part.get("text") is not None:
            text_parts[pid] = part["text"]
        elif part.get("type") == "tool":
            state = part.get("state") or {}
            tool_parts[pid] = {
                "tool": part.get("tool"),
                "status": state.get("status"),
                "input": state.get("input"),
                "output_head": str(state.get("output"))[:500] if state.get("output") is not None else None,
            }
    final_text = "\n\n".join(text_parts[p] for p in order if p in text_parts)
    tool_calls = [tool_parts[p] for p in order if p in tool_parts]
    return final_text, tool_calls


CONTINUE_MSG = ("Give your final, complete answer to the original question now, "
                "based on everything you have found so far. Do not call any more tools.")

# an attempt "ends unanswered" when it is short OR reads as investigation
# narration with no conclusion (length alone missed diag-006 in round 3)
INCONCLUSIVE_RE = re.compile(
    r"(?i)(let me|now let me|now i(?:'|’)ll|i(?:'|’)ll (?:check|look|read|search|probe|dig)|"
    r"next,? i)\b[^.]{0,120}$|[:;]\s*$")


def ends_unanswered(text):
    if len(text) < 300:
        return True
    tail = text.rstrip()[-250:]
    return bool(INCONCLUSIVE_RE.search(tail))


def _invoke(cmd, workdir, env, timeout):
    try:
        proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True,
                              timeout=timeout, env=env)
        return proc.stdout, proc.stderr, proc.returncode, "ok"
    except subprocess.TimeoutExpired as ex:
        stdout = ex.stdout.decode() if isinstance(ex.stdout, bytes) else (ex.stdout or "")
        stderr = ex.stderr.decode() if isinstance(ex.stderr, bytes) else (ex.stderr or "")
        return stdout, stderr, -1, "timeout"


def run_card(card, args, attempts_dir):
    adir = attempts_dir / card["id"]
    workdir = adir / "workdir"
    workdir.mkdir(parents=True, exist_ok=True)
    if args.kb:
        kb_dst = workdir / "kb"
        if not kb_dst.exists():
            shutil.copytree(args.kb, kb_dst)
    msg = PREAMBLE + card["input"]
    base = ["opencode", "run", "-m", args.model, "--agent", args.agent,
            "--format", "json", "--auto"]
    if args.pure:
        base.append("--pure")
    env = dict(os.environ)
    if args.oc_config:
        env["OPENCODE_CONFIG"] = args.oc_config
    t0 = time.time()
    stdout, stderr, rc, status = _invoke(base + [msg], workdir, env, args.timeout)
    events, noise = parse_events(stdout.splitlines())
    final_text, tool_calls = extract(events)
    continued = False

    # end-without-answer backstop: continue the session and demand the answer
    if status == "ok" and ends_unanswered(final_text):
        sid = next((e.get("sessionID") for e in events if e.get("sessionID")), None)
        if sid:
            continued = True
            out2, err2, rc2, st2 = _invoke(base + ["-s", sid, CONTINUE_MSG],
                                           workdir, env, min(args.timeout, 300))
            stdout += "\n" + out2
            stderr += "\n" + err2
            events, noise = parse_events(stdout.splitlines())
            final_text, tool_calls = extract(events)
            if st2 == "timeout":
                status = "timeout"
    duration = round(time.time() - t0, 1)

    (adir / "trajectory.jsonl").write_text(stdout)
    (adir / "err.log").write_text(stderr)
    if status == "ok" and not final_text:
        status = "empty"
    attempt = {
        "task_id": card["id"],
        "category": card["category"],
        "model": args.model,
        "agent": args.agent,
        "status": status,
        "continued": continued,
        "exit_code": rc,
        "duration_s": duration,
        "n_events": len(events),
        "n_noise_lines": len(noise),
        "tool_calls": tool_calls,
        "final_text": final_text,
    }
    (adir / "attempt.json").write_text(json.dumps(attempt, indent=1))
    return attempt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--agent", default="plan")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--oc-config", help="path exported as OPENCODE_CONFIG for the run")
    ap.add_argument("--kb", help="knowledge-base dir copied into each attempt workdir as kb/")
    ap.add_argument("--pure", action="store_true", default=True,
                    help="pass --pure to opencode (skip external plugins; default on)")
    ap.add_argument("--no-pure", dest="pure", action="store_false")
    args = ap.parse_args()

    cards = load_cards(args.cards, args.only)
    attempts_dir = pathlib.Path(args.out) / "attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)
    print(f"running {len(cards)} cards | model={args.model} agent={args.agent}", flush=True)

    summary = []
    for i, card in enumerate(cards, 1):
        a = run_card(card, args, attempts_dir)
        summary.append(a)
        print(f"[{i}/{len(cards)}] {card['id']} {a['status']} {a['duration_s']}s "
              f"tools={len(a['tool_calls'])} text={len(a['final_text'])}ch", flush=True)

    (pathlib.Path(args.out) / "run.json").write_text(json.dumps({
        "model": args.model, "agent": args.agent, "cards": args.cards,
        "attempts": [{k: a[k] for k in ("task_id", "status", "duration_s")} for a in summary],
    }, indent=1))
    n_ok = sum(1 for a in summary if a["status"] == "ok")
    print(f"done: {n_ok}/{len(summary)} completed cleanly -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
