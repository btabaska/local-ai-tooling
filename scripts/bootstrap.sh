#!/usr/bin/env bash
# bootstrap.sh — Run the whole setup in order. Review each script first; this just chains them.
# Run from the repo root:  ./scripts/bootstrap.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "### Step 0: preflight"
bash scripts/00-preflight.sh
read -rp "Continue? [y/N] " ok; [[ "$ok" == "y" ]] || exit 0

echo "### Step 1: tune + expose Ollama"
bash scripts/01-ollama-tune.sh

echo "### Step 2: firewall (edit LAN_SUBNET inside first if you haven't!)"
bash scripts/02-firewall.sh

echo "### Step 3: build model variants (this pulls a few GB)"
bash scripts/03-model-variants.sh

echo "### Step 4: docker stack"
if [[ ! -f docker/.env ]]; then
  echo "docker/.env missing. Creating from template — EDIT IT with real secrets, then re-run."
  cp docker/.env.example docker/.env
  echo "Generate secrets with: openssl rand -hex 32"
  exit 1
fi
( cd docker && docker compose up -d )   # bundled Caddy is OFF by default (it's profiled out)
echo "   HTTPS on this box is opt-in: 'cd docker && docker compose --profile caddy up -d'."
echo "   Using your own reverse proxy instead? Leave Caddy off; point it at this host:3000."

echo
echo "### Done. Running healthcheck…"
bash scripts/healthcheck.sh
