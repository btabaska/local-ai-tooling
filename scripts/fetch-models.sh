#!/usr/bin/env bash
# scripts/fetch-models.sh — rebuild /opt/llm/models from docker/models.manifest.yaml (ai-06).
#
# "Rebuild the rig after an NVMe loss" as a runnable, idempotent path. The model
# weights are DELIBERATELY outside restic (too large); this script + the manifest
# ARE their disaster-recovery record. For every served GGUF it:
#   1. skips the file if it already exists AND its sha256 matches the manifest,
#   2. otherwise downloads it from Hugging Face (huggingface-cli / hf),
#   3. renames to the on-disk name the llama-swap config expects, and
#   4. verifies the sha256 — refusing to install a mismatched file.
#
# The sha256 in each entry is the ground truth. Where an upstream file was
# renamed on disk (source.confidence: inferred), the HF filename is the best
# known match; if a download's sha256 does not match, list the repo
# (`huggingface-cli download <repo> --local-dir …`) and pick the file whose
# sha256 equals the manifest value.
#
# Usage:  ./scripts/fetch-models.sh [--dry-run]   (run ON the rig)
# Requires: huggingface-cli or hf  (pipx install huggingface_hub[cli]);
#           HF_TOKEN in env only if a repo is gated.
set -euo pipefail

MODELS_DIR="${MODELS_DIR:-/opt/llm/models}"
DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

# Resolve a HF download CLI (new `hf` or legacy `huggingface-cli`).
if command -v huggingface-cli >/dev/null 2>&1; then
  HF() { huggingface-cli download "$@"; }
elif command -v hf >/dev/null 2>&1; then
  HF() { hf download "$@"; }
else
  echo "ERROR: need huggingface-cli or hf on PATH (pipx install 'huggingface_hub[cli]')" >&2
  exit 1
fi

mkdir -p "$MODELS_DIR"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

# fetch REPO REMOTE_FILE DEST_NAME SHA256
fetch() {
  local repo="$1" remote="$2" dest="$3" want="$4"
  local target="$MODELS_DIR/$dest"

  if [[ -f "$target" ]]; then
    local have; have="$(sha256sum "$target" | awk '{print $1}')"
    if [[ "$have" == "$want" ]]; then
      echo "OK    $dest  (present, sha256 matches — skip)"
      return 0
    fi
    echo "STALE $dest  (present but sha256 mismatch — re-downloading)"
  fi

  if [[ "$DRY_RUN" == 1 ]]; then
    echo "PLAN  $dest  <-  $repo :: $remote"
    return 0
  fi

  echo "GET   $dest  <-  $repo :: $remote"
  HF "$repo" "$remote" --local-dir "$tmp" >/dev/null
  local src; src="$(find "$tmp" -type f -name "$(basename "$remote")" | head -1)"
  [[ -n "$src" ]] || { echo "ERROR: $remote not found in download of $repo" >&2; return 1; }

  local got; got="$(sha256sum "$src" | awk '{print $1}')"
  if [[ "$got" != "$want" ]]; then
    echo "ERROR: sha256 mismatch for $dest" >&2
    echo "  want $want" >&2
    echo "  got  $got"  >&2
    echo "  (upstream file was likely renamed/updated — download the whole repo and" >&2
    echo "   pick the file whose sha256 == the manifest value.)" >&2
    return 1
  fi
  mv -f "$src" "$target"
  echo "DONE  $dest  (sha256 verified)"
}

echo "== Restoring served GGUFs into $MODELS_DIR =="

# --- Coding / agentic ---
fetch unsloth/Qwen3.6-35B-A3B-GGUF \
      Qwen3.6-35B-A3B-UD-IQ4_NL_XL.gguf \
      Qwen3.6-35B-A3B-UD-IQ4_NL_XL.gguf \
      071ee2a008ec51372f990d8efbea92ec9dd0137974110ef68fbfde429c8c6dd4

fetch unsloth/Qwen3.6-27B-GGUF \
      Qwen3.6-27B-MTP-UD-Q4_K_XL.gguf \
      Qwen3.6-27B-MTP-UD-Q4_K_XL.gguf \
      4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095

fetch unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF \
      Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf \
      qwen3-coder-30b.gguf \
      2841aa314d916434860cfb8990347528dcdfe5c350dbcb9d1461dbee88ff2533

fetch unsloth/Devstral-Small-2505-GGUF \
      Devstral-Small-2505-UD-Q4_K_XL.gguf \
      devstral-24b.gguf \
      d8d48447e4de4c6ffab551d77c48d0898b50ea5d2b7f71ebf48332a7cb58c9a6

# --- Chat ---
fetch unsloth/gemma-4-31b-it-qat-GGUF \
      gemma-4-31b-it-qat-Q4_0.gguf \
      gemma4-31b-qat.gguf \
      9188a71055550f1e60b875d02b7abb63625ac11b4a6f148d6b22b3b28ba3d335

# deckard-heretic: DavidAU GGUF — exact repo/file not embedded in the header.
# Confirm the repo on HF and set REMOTE below; the sha256 gate is authoritative.
fetch DavidAU/PLACEHOLDER-Gemma-4-31B-DECKARD-HERETIC-UNCENSORED-Thinking-GGUF \
      DECKARD-HERETIC.Q4_K_M.gguf \
      deckard-heretic.gguf \
      577a97c78011b40d03a1902495b5c1029b8502c8f935397317de9a8133e51cf7

# --- Creative / roleplay (Mistral-Small-24B family + shared vision projector) ---
fetch TheDrummer/Cydonia-24B-v4.3-GGUF \
      Cydonia-24B-v4zg-Q5_K_M.gguf \
      cydonia-24b.gguf \
      7ebb97a585738cd586b90eb3474f958b9a3c0ed63fe256e75812c1d8356a1d86

fetch bartowski/cognitivecomputations_Dolphin-Mistral-24B-Venice-Edition-GGUF \
      cognitivecomputations_Dolphin-Mistral-24B-Venice-Edition-Q5_K_M.gguf \
      dolphin-venice-24b.gguf \
      ff3f4feb80bca6b4755405632092ede76a0e8f9c05af64d6e76d25737adc1909

fetch mradermacher/Goetia-24B-v1.3-GGUF \
      Goetia-24B-v1.3.Q5_K_M.gguf \
      goetia-24b.gguf \
      80b6c1d16e0ddb3ac764a246e1ad628b6259c6878d2580a528055965a5182f6f

fetch unsloth/Mistral-Small-3.2-24B-Instruct-2506-GGUF \
      mmproj-F16.gguf \
      mmproj-mistral-small-3.2-f16.gguf \
      d6af684ae9136398eaa0b59ea9e0b0b850bb6ac5084f1e8c5cb8f85251825eaf

# --- Small / utility ---
fetch Qwen/Qwen2.5-Coder-7B-Instruct-GGUF \
      qwen2.5-coder-7b-instruct-q4_k_m.gguf \
      qwen2.5-coder-7b.gguf \
      1664fccab734674a50763490a8c6931b70e3f2f8ec10031b54806d30e5f956b6

fetch unsloth/Llama-3.2-3B-Instruct-GGUF \
      Llama-3.2-3B-Instruct-Q4_K_M.gguf \
      llama3.2-3b.gguf \
      2ca38452bd9f4348251abbc3f8234ecf0ddf9b96bfcbe639d4375b2721175d0b

# --- Embeddings ---
fetch Qwen/Qwen3-Embedding-0.6B-GGUF \
      Qwen3-Embedding-0.6B-Q8_0.gguf \
      Qwen3-Embedding-0.6B-Q8_0.gguf \
      06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439

echo
echo "== Ollama shim (separate store; not /opt/llm/models) =="
echo "  ollama pull llama3.2:3b"
echo "  ollama pull nomic-embed-text"
echo "  printf 'FROM llama3.2:3b\\nPARAMETER num_ctx 8192\\nPARAMETER temperature 0\\n' > /tmp/Modelfile.tag && ollama create tag:fast -f /tmp/Modelfile.tag"
echo
echo "Done. Verify: cd $MODELS_DIR && sha256sum -c <(...)  or re-run this script (all rows should say OK)."
