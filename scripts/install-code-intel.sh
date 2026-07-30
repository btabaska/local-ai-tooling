#!/usr/bin/env bash
# install-code-intel.sh — language servers + deterministic code-intelligence tools
# for the local coding agents (ai-10, Tier 1).
#
# WHY: a 35B local model cannot hold a large codebase in context. Deterministic
# tooling (LSP diagnostics, type checkers, structural search) substitutes for raw
# model capability — it is the cheapest force-multiplier available. opencode's
# edit/write tools feed LSP diagnostics straight back into the tool result the
# model reads, but only if a server is actually installed for that language.
#
# Runs on BOTH targets:
#   - the rig (CachyOS/Arch) — where opencode runs under Orca over SSH
#   - a MacBook (Homebrew)   — the fallback client
#
# opencode auto-installs some servers on demand; the ones here are the common
# gaps plus the CLI tools the verify hook (agentic/opencode/plugins/local-llm.ts)
# and AGENTS.md conventions depend on.
#
# Usage:  ./scripts/install-code-intel.sh [--dry-run] [--minimal]
set -euo pipefail

DRY_RUN=0
MINIMAL=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --minimal) MINIMAL=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

run() {
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "  DRY-RUN: $*"
  else
    echo "  + $*"
    "$@"
  fi
}

have() { command -v "$1" >/dev/null 2>&1; }

# --- core set: the highest impact-per-byte tools, installed on every host ------
# ripgrep/fd   : agent search primitives (NOTE: use `rg -l` / `rg -n`, never
#                `rg --json` — measured 32x the tokens for identical information)
# ast-grep     : structural search/replace; lets the model refactor without
#                reading whole files
# just         : the single verify-command entry point the plugin looks for
# shellcheck   : this repo is mostly shell; the only linter that applies here
CORE_ARCH=(ripgrep fd ast-grep just shellcheck bash-language-server yaml-language-server taplo-cli python-yaml)
CORE_BREW=(ripgrep fd ast-grep just shellcheck bash-language-server yaml-language-server taplo pyyaml)

# --- language set: only meaningful in repos that use them ---------------------
LANG_ARCH=(pyright ruff gopls rust-analyzer typescript-language-server marksman)
LANG_BREW=(pyright ruff gopls rust-analyzer typescript-language-server marksman)

OS="$(uname -s)"
echo "==> host: $OS  (dry-run=$DRY_RUN minimal=$MINIMAL)"

case "$OS" in
  Linux)
    if ! have pacman; then
      echo "ERROR: expected an Arch-based host (pacman not found)." >&2
      exit 1
    fi
    PKGS=("${CORE_ARCH[@]}")
    [[ $MINIMAL -eq 0 ]] && PKGS+=("${LANG_ARCH[@]}")
    echo "==> pacman: ${PKGS[*]}"
    run sudo pacman -S --needed --noconfirm "${PKGS[@]}"

    # basedpyright is a strictly better pyright for agent use (faster, stricter
    # inference) but lives in the AUR. Optional — skip silently without a helper.
    if [[ $MINIMAL -eq 0 ]]; then
      if have paru;   then run paru   -S --needed --noconfirm basedpyright-bin || true
      elif have yay;  then run yay    -S --needed --noconfirm basedpyright-bin || true
      else echo "  (skip basedpyright-bin: no paru/yay found)"; fi
    fi
    ;;
  Darwin)
    if ! have brew; then
      echo "ERROR: Homebrew not found. Install from https://brew.sh first." >&2
      exit 1
    fi
    PKGS=("${CORE_BREW[@]}")
    [[ $MINIMAL -eq 0 ]] && PKGS+=("${LANG_BREW[@]}")
    echo "==> brew: ${PKGS[*]}"
    run brew install "${PKGS[@]}"
    ;;
  *)
    echo "ERROR: unsupported OS: $OS" >&2
    exit 1
    ;;
esac

# --- verification -------------------------------------------------------------
echo
echo "==> resolving installed tools"
MISSING=0
for b in rg fd ast-grep just shellcheck bash-language-server yaml-language-server; do
  if have "$b"; then
    printf '  %-26s OK\n' "$b"
  else
    printf '  %-26s MISSING\n' "$b"; MISSING=1
  fi
done
if [[ $MINIMAL -eq 0 ]]; then
  for b in pyright basedpyright ruff gopls rust-analyzer typescript-language-server marksman; do
    have "$b" && printf '  %-26s OK\n' "$b" || printf '  %-26s absent (ok if unused)\n' "$b"
  done
fi

cat <<'EOF'

==> next steps
  1. Deploy the client config + verify plugin:
       cp opencode.json                        ~/.config/opencode/opencode.json
       mkdir -p ~/.config/opencode/plugins
       cp agentic/opencode/plugins/local-llm.ts ~/.config/opencode/plugins/

  2. Give each real project a `verify-fast` recipe so the plugin has one command
     name to call (it silently disables itself when none is found):

       # justfile
       verify-fast:
           ruff check . && tsc --noEmit

     Or drop an executable .opencode/verify.sh, or export OPENCODE_VERIFY_CMD.

  3. Confirm the loop actually fires: edit a file so it breaks typecheck, and
     check the tool result contains a <verify status="fail"> block.
EOF

[[ $MISSING -eq 1 ]] && { echo; echo "WARNING: some core tools are missing (see above)."; exit 1; }
exit 0
