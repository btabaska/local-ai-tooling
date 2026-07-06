#!/usr/bin/env bash
# 03-model-variants.sh — Create purpose-tuned model variants + pull small helper/embedding models.
# Why variants? Context length and temperature are baked per USE CASE so each tool gets the right
# behavior without a global setting that wastes VRAM.
set -euo pipefail

echo "== Building purpose-tuned Ollama models =="

# 1) CODING model for OpenCode — needs 64k+ context; low temp helps tool-calling reliability.
#    Adjust the FROM line if your primary coder changes.
echo "-> code:opencode  (64k ctx, temp 0.1, from qwen3-coder:30b)"
cat > /tmp/Modelfile.code <<'EOF'
FROM qwen3-coder:30b
PARAMETER num_ctx 65536
PARAMETER temperature 0.1
PARAMETER top_p 0.8
EOF
ollama create code:opencode -f /tmp/Modelfile.code
echo "   NOTE: 18GB weights + 64k KV is tight on 24GB. After first use run 'ollama ps'."
echo "   If it shows any CPU/RAM offload, rebuild with num_ctx 49152 or 32768."

# 2) TAGGING / utility model for Obsidian AI Tagger + OpenCode session titles.
#    Deterministic (temp 0), small context — fast and frees VRAM for the big models.
#    Requires a small base model; we pull llama3.2:3b (swap for a 4B gemma4 if you prefer).
echo "-> pulling small utility base (llama3.2:3b)…"
ollama pull llama3.2:3b
echo "-> tag:fast  (8k ctx, temp 0, from llama3.2:3b)"
cat > /tmp/Modelfile.tag <<'EOF'
FROM llama3.2:3b
PARAMETER num_ctx 8192
PARAMETER temperature 0
EOF
ollama create tag:fast -f /tmp/Modelfile.tag

# 3) EMBEDDINGS for Open WebUI RAG + Obsidian Smart Connections.
echo "-> pulling embedding model (nomic-embed-text)…"
ollama pull nomic-embed-text

# 4) OPTIONAL: reliable coding fallback (Devstral) for when a model mangles tool calls.
#    Uncomment to enable; ~14GB.
# echo "-> pulling devstral fallback…"
# ollama pull devstral:24b

echo
echo "== Result =="
ollama list
echo
echo "Your stable, purpose-named handles are now: code:opencode, tag:fast, nomic-embed-text"
echo "plus your existing chat models (gemma4:31b-it-qat, deckard-heretic:128k, …)."
