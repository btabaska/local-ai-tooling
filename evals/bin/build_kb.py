#!/usr/bin/env python3
"""Build the eval knowledge base (kb/) from Claude-side memory + CLAUDE.md.

Usage: python3 build_kb.py [--out evals/kb]

Packages, for the local eval agent to grep/read with its file tools:
  kb/INDEX.md          — one-line-per-topic index (from MEMORY.md) + usage note
  kb/quirks/<name>.md  — the per-topic memory files verbatim
  kb/CLAUDE-context.md — fleet-wide operating rules (repo CLAUDE.md)

Excluded: local-ai-eval-loop.md (describes this eval project itself — giving it
to the candidate would leak eval design). Output is gitignored — the kb is a
build artifact regenerated per loop, not committed content.

A light secret scan warns on suspicious high-entropy tokens; memory policy keeps
secret VALUES out of these files (key PATHS like `vault ai_stack.foo` are fine).
"""
import argparse
import pathlib
import re
import shutil
import sys

MEMORY_DIR = pathlib.Path.home() / ".claude/projects/-Users-brandontabaska-GitHub-Home/memory"
CLAUDE_MD = pathlib.Path.home() / "GitHub/Home/CLAUDE.md"
WIKI_DIR = pathlib.Path.home() / "GitHub/Home/foss-setup/wiki/docs"
EXCLUDE = {"local-ai-eval-loop.md", "MEMORY.md"}

SECRET_RE = re.compile(r"(eyJ[A-Za-z0-9_-]{20,}|[A-Za-z0-9+/]{40,}={0,2}|[0-9a-f]{40,})")

HEADER = """# Homelab knowledge base — index

One line per known quirk/hazard, distilled from real past incidents. When a
question touches any of these topics, read the full note at kb/quirks/<name>.md
(the link name matches the file name) BEFORE theorizing — these notes record the
verified mechanism and fix, and they override general intuition. Fleet-wide
operating rules are in kb/CLAUDE-context.md.

The homelab's FULL documentation wiki is in kb/wiki/ — runbooks/ (per-incident
procedures), services/ (per-service pages), architecture/ (design decisions,
network/DNS/backup layouts), reference/, operations/, hosts/. If the quirk notes
below don't cover a topic, grep kb/wiki/ next — most services, chains and past
incidents are documented there.

"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(pathlib.Path(__file__).parent.parent / "kb"))
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    (out / "quirks").mkdir(parents=True)

    warns = []
    copied = 0
    for f in sorted(MEMORY_DIR.glob("*.md")):
        if f.name in EXCLUDE:
            continue
        text = f.read_text()
        for m in SECRET_RE.finditer(text):
            if m.group(0).count("/") >= 2:  # path-like, not a secret
                continue
            warns.append(f"{f.name}: suspicious token {m.group(0)[:12]}…")
        (out / "quirks" / f.name).write_text(text)
        copied += 1

    index = (MEMORY_DIR / "MEMORY.md").read_text()
    index = "\n".join(l for l in index.splitlines()
                      if "local-ai-eval-loop" not in l and not l.startswith("# "))
    runbooks = sorted((WIKI_DIR / "runbooks").glob("*.md")) if WIKI_DIR.is_dir() else []
    rb_lines = ["", "## Wiki runbooks (kb/wiki/runbooks/) — read the specific file, don't shotgun-grep", ""]
    rb_lines += [f"- {f.name}" for f in runbooks if f.name != "index.md"]
    (out / "INDEX.md").write_text(HEADER + index.strip() + "\n" + "\n".join(rb_lines) + "\n")
    (out / "CLAUDE-context.md").write_text(CLAUDE_MD.read_text())
    # full wiki (committed, already-sanitized repo docs — no secret scan needed)
    n_wiki = 0
    if WIKI_DIR.is_dir():
        shutil.copytree(WIKI_DIR, out / "wiki",
                        ignore=shutil.ignore_patterns("roadmap", "*.png", "*.jpg", "*.svg"))
        n_wiki = sum(1 for _ in (out / "wiki").rglob("*.md"))

    print(f"kb built: {copied} quirk notes + {n_wiki} wiki pages + index + CLAUDE-context -> {out}")
    if warns:
        print("SECRET-SCAN WARNINGS (review before shipping):", file=sys.stderr)
        for w in warns:
            print(f"  {w}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
