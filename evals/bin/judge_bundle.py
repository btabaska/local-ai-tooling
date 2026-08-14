#!/usr/bin/env python3
"""Re-extract attempts from raw trajectories and build the judging bundle.

Usage:
  python3 judge_bundle.py --cards <cards.jsonl> --results <results-dir>

Reads results/attempts/<id>/trajectory.jsonl, re-parses with the current extractor
(rewriting each attempt.json), then writes results/judging.json — one record per card
joining {input, reference, checklist, recapture_cmd} with the candidate's
{final_text, tool_calls, duration}. The judge (frontier model) grades from that bundle;
the candidate's text never includes reference/checklist, and vice versa nothing leaks
back into datasets.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from run_eval import parse_events, extract  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", required=True)
    ap.add_argument("--results", required=True)
    args = ap.parse_args()

    cards = {c["id"]: c for c in (json.loads(l) for l in open(args.cards) if l.strip())}
    results = pathlib.Path(args.results)
    bundle = []
    for cid, card in cards.items():
        adir = results / "attempts" / cid
        traj = adir / "trajectory.jsonl"
        if not traj.exists():
            bundle.append({"id": cid, "status": "missing"})
            continue
        raw = traj.read_text()
        events, noise = parse_events(raw.splitlines())
        final_text, tool_calls = extract(events)
        # contamination detector: any tool call that reached into the eval kit's
        # own datasets means judge-only reference text may have entered context
        contaminated = []
        for e in events:
            part = e.get("part") or {}
            if part.get("type") == "tool":
                inp = json.dumps((part.get("state") or {}).get("input") or {})
                if "cards.jsonl" in inp or "/datasets" in inp or "datasets/" in inp:
                    contaminated.append(f"{part.get('tool')}: {inp[:120]}")
        attempt_path = adir / "attempt.json"
        attempt = json.loads(attempt_path.read_text()) if attempt_path.exists() else {}
        attempt.update({
            "final_text": final_text,
            "tool_calls": tool_calls,
            "status": attempt.get("status") if attempt.get("status") in ("timeout",) else ("ok" if final_text else "empty"),
        })
        attempt_path.write_text(json.dumps(attempt, indent=1))
        bundle.append({
            "id": cid,
            "category": card["category"],
            "difficulty": card["difficulty"],
            "status": attempt["status"],
            "contamination": contaminated,
            "duration_s": attempt.get("duration_s"),
            "input": card["input"],
            "reference": card["reference"],
            "checklist": card["checklist"],
            "recapture_cmd": card.get("recapture_cmd"),
            "candidate_text": final_text,
            "tool_calls": tool_calls,
        })
    out = results / "judging.json"
    out.write_text(json.dumps(bundle, indent=1))
    ok = sum(1 for b in bundle if b.get("status") == "ok")
    print(f"bundle: {len(bundle)} cards, {ok} ok -> {out}")
    dirty = [b["id"] for b in bundle if b.get("contamination")]
    if dirty:
        print(f"CONTAMINATION WARNING — tool calls reached eval datasets on: {dirty}")


if __name__ == "__main__":
    main()
