#!/usr/bin/env bash
# 02-firewall.sh — Restrict the AI ports to your LAN only (Ollama has no auth of its own).
# Edit LAN_SUBNET to match your network, then run.
set -euo pipefail

# ---- EDIT THIS ----
LAN_SUBNET="192.168.1.0/24"   # e.g. 192.168.1.0/24, 10.0.0.0/24, etc.
# -------------------

PORTS=(11434 4000 3000 8000)  # ollama, litellm, open-webui, mcpo

echo "Restricting ports ${PORTS[*]} to ${LAN_SUBNET} …"

if command -v ufw >/dev/null 2>&1 && sudo ufw status >/dev/null 2>&1; then
  echo "Using ufw."
  for p in "${PORTS[@]}"; do
    sudo ufw allow from "$LAN_SUBNET" to any port "$p" proto tcp
  done
  echo "ufw rules added. (Enable ufw if not already: sudo ufw enable)"

elif command -v firewall-cmd >/dev/null 2>&1 && sudo firewall-cmd --state >/dev/null 2>&1; then
  echo "Using firewalld (rich rules scoped to ${LAN_SUBNET})."
  for p in "${PORTS[@]}"; do
    sudo firewall-cmd --permanent --add-rich-rule="rule family=ipv4 source address=${LAN_SUBNET} port port=${p} protocol=tcp accept"
  done
  sudo firewall-cmd --reload
  echo "firewalld rules added."

else
  cat <<EOF
No ufw/firewalld detected (common on a bare CachyOS install).
If you have no host firewall, your LAN router is your only boundary — acceptable for a
home LAN you trust, but consider installing one:

  sudo pacman -S ufw && sudo systemctl enable --now ufw
  # then re-run this script

Or add nftables rules manually, e.g.:
  table inet filter {
    chain input {
      type filter hook input priority 0; policy drop;
      ct state established,related accept
      iif "lo" accept
      ip saddr ${LAN_SUBNET} tcp dport { $(IFS=,; echo "${PORTS[*]}") } accept
      # ...your other rules...
    }
  }
EOF
fi

echo
echo "Reminder: do NOT port-forward any of these to the internet. For remote access,"
echo "use Tailscale (see README) — it needs no open ports."
