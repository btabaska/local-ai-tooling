#!/usr/bin/env bash
# 00-preflight.sh — Verify the CachyOS AI server is ready before we configure anything.
# Safe to run repeatedly. Makes NO changes.
set -uo pipefail

pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$1"; }

echo "== Local AI Stack :: preflight =="

# --- GPU ---
if command -v nvidia-smi >/dev/null 2>&1; then
  gpu=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)
  pass "NVIDIA GPU: ${gpu}"
else
  fail "nvidia-smi not found — install NVIDIA drivers (CachyOS: they're usually preinstalled)."
fi

# --- Ollama ---
if command -v ollama >/dev/null 2>&1; then
  pass "ollama binary: $(ollama --version 2>/dev/null | head -1)"
else
  fail "ollama not found on PATH."
fi
if systemctl is-active --quiet ollama 2>/dev/null; then
  pass "ollama.service is active"
else
  warn "ollama.service not active (you may be running 'ollama serve' manually)."
fi

# --- Docker ---
if command -v docker >/dev/null 2>&1; then
  pass "docker: $(docker --version)"
  if docker compose version >/dev/null 2>&1; then
    pass "docker compose v2: $(docker compose version --short 2>/dev/null)"
  else
    fail "docker compose v2 plugin missing. CachyOS: sudo pacman -S docker-compose"
  fi
  if ! docker info >/dev/null 2>&1; then
    warn "cannot talk to docker daemon — is it enabled? sudo systemctl enable --now docker ; and add yourself: sudo usermod -aG docker \$USER (re-login)."
  fi
else
  fail "docker not found. CachyOS: sudo pacman -S docker docker-compose && sudo systemctl enable --now docker"
fi

# --- Ports ---
check_port() {
  if ss -tlnp 2>/dev/null | grep -q ":$1 "; then
    warn "port $1 already in use ($2). Existing service will conflict unless it IS $2."
  else
    pass "port $1 free ($2)"
  fi
}
check_port 11434 "ollama"
check_port 4000  "litellm"
check_port 3000  "open-webui"
check_port 8000  "mcpo"

# --- Networking ---
ip=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')
host=$(hostname)
echo
echo "== Networking =="
pass "This server's LAN IP: ${ip:-<unknown>}"
pass "Hostname: ${host}  (mDNS name likely: ${host}.local)"
echo
echo "Set AI_HOST to one of the above in docker/.env and your client configs."
echo "A DHCP reservation for ${ip:-this IP} on your router is strongly recommended."
