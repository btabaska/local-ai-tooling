#!/usr/bin/env python3
"""Emit the candidate-visible half of a card set.

Usage: python3 public_cards.py --cards <cards.jsonl> [--out <cards.public.jsonl>]

The rig-side runner only needs {id, category, tier, input, context_policy}.
References and checklists are judge-only and MUST NOT be shipped to the machine
the candidate runs on: in the 2026-08-14 loop-2 run a candidate's recursive grep
over the eval kit surfaced a card's reference text into its own context
(verify-010, scored contaminated). Ship THIS file to the rig, keep the full
cards Mac-side for judging.
"""
import argparse
import json

PUBLIC_FIELDS = ("id", "category", "tier", "input", "context_policy")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    out = args.out or args.cards.replace(".jsonl", ".public.jsonl")
    if out == args.cards:
        raise SystemExit("refusing to overwrite the full card set")
    n = 0
    with open(out, "w") as fh:
        for line in open(args.cards):
            if not line.strip():
                continue
            c = json.loads(line)
            fh.write(json.dumps({k: c[k] for k in PUBLIC_FIELDS if k in c}) + "\n")
            n += 1
    print(f"{n} public cards -> {out}")


if __name__ == "__main__":
    main()
