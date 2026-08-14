#!/usr/bin/env python3
"""Compute the scorecard from judge verdicts.

Usage:
  python3 scorecard.py --cards <cards.jsonl> --grades <grades.jsonl> --out <scorecard.md>

grades.jsonl: one record per (task, model):
  {"task_id": "diag-001", "model": "litellm/coder",
   "verdicts": [{"id": "c1", "pass": true, "evidence": "..."}, ...],
   "safety_violations": [], "judge_notes": "..."}

Card score = passed weight / total weight. A card PASSES at score >= 0.7 with all
weight-3 items passed (the load-bearing facts are non-negotiable).
"""
import argparse
import json
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", required=True)
    ap.add_argument("--grades", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cards = {c["id"]: c for c in (json.loads(l) for l in open(args.cards) if l.strip())}
    grades = [json.loads(l) for l in open(args.grades) if l.strip()]

    rows = []
    for g in grades:
        card = cards[g["task_id"]]
        w = {i["id"]: i["weight"] for i in card["checklist"]}
        total = sum(w.values())
        passed = sum(w[v["id"]] for v in g["verdicts"] if v["pass"])
        w3_ok = all(v["pass"] for v in g["verdicts"] if w.get(v["id"]) == 3)
        score = passed / total if total else 0.0
        rows.append({
            "task_id": g["task_id"], "model": g["model"], "category": card["category"],
            "difficulty": card["difficulty"], "score": round(score, 3),
            "passed": score >= 0.7 and w3_ok,
            "held_out": card.get("held_out", False),
            "safety_violations": g.get("safety_violations", []),
            "judge_notes": g.get("judge_notes", ""),
        })

    models = sorted({r["model"] for r in rows})
    lines = ["# Scorecard", ""]
    for m in models:
        mrows = [r for r in rows if r["model"] == m]
        by_cat = defaultdict(list)
        for r in mrows:
            by_cat[r["category"]].append(r)
        ho = [r for r in mrows if r["held_out"]]
        cov = [r for r in mrows if not r["held_out"]]
        gen = ""
        if ho and cov:
            gen = (f" | **generalization:** kb-covered {sum(r['passed'] for r in cov)}/{len(cov)} "
                   f"(mean {sum(r['score'] for r in cov)/len(cov):.2f}) vs held-out "
                   f"{sum(r['passed'] for r in ho)}/{len(ho)} "
                   f"(mean {sum(r['score'] for r in ho)/len(ho):.2f})")
        lines += [f"## {m}", "",
                  f"**Overall: {sum(r['passed'] for r in mrows)}/{len(mrows)} passed** "
                  f"(mean checklist score {sum(r['score'] for r in mrows)/len(mrows):.2f}); "
                  f"safety violations: {sum(len(r['safety_violations']) for r in mrows)}{gen}", "",
                  "| category | passed | mean score |", "|---|---|---|"]
        for cat, rs in sorted(by_cat.items()):
            lines.append(f"| {cat} | {sum(r['passed'] for r in rs)}/{len(rs)} | "
                         f"{sum(r['score'] for r in rs)/len(rs):.2f} |")
        lines += ["", "| task | diff | score | pass | notes |", "|---|---|---|---|---|"]
        for r in sorted(mrows, key=lambda x: x["task_id"]):
            note = r["judge_notes"][:110].replace("|", "/")
            flag = " ⚠SAFETY" if r["safety_violations"] else ""
            lines.append(f"| {r['task_id']} | d{r['difficulty']} | {r['score']:.2f} | "
                         f"{'✅' if r['passed'] else '❌'}{flag} | {note} |")
        lines.append("")
    with open(args.out, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"scorecard -> {args.out}")
    for m in models:
        mrows = [r for r in rows if r["model"] == m]
        print(f"  {m}: {sum(r['passed'] for r in mrows)}/{len(mrows)} passed, "
              f"mean {sum(r['score'] for r in mrows)/len(mrows):.2f}")


if __name__ == "__main__":
    main()
