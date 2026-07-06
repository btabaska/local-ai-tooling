# INSTRUCTIONS — set up the rig, connect from the MacBook

Follow top to bottom. Phase 1 runs once on the CachyOS rig; Phase 2 is your work MacBook.
For the reasoning behind any choice, see `README.md` (base stack) and `agentic/README.md` (agent layer).

---

## Phase 1 — On the rig (CachyOS), one time

Prereqs: NVIDIA drivers, **Ollama**, **Docker + compose v2**, and **Tailscale** (logged in). The
preflight script checks all of these.

```bash
cd local-ai-tooling
chmod +x scripts/*.sh agentic/scripts/*.sh
./scripts/00-preflight.sh            # checks GPU/Ollama/Docker/ports — makes NO changes
```

### 1. Secrets

```bash
cp docker/.env.example docker/.env
openssl rand -hex 32   # LITELLM_MASTER_KEY  (prefix with sk-)
openssl rand -hex 32   # LITELLM_SALT_KEY    (prefix sk-; NEVER change after adding models)
openssl rand -hex 32   # WEBUI_SECRET_KEY    (keep stable forever)
$EDITOR docker/.env     # paste the secrets; set AI_HOST and WEBUI_URL (see step 5 for WEBUI_URL)
```

### 2. Firewall subnet

```bash
$EDITOR scripts/02-firewall.sh       # set LAN_SUBNET to your real network (default is 192.168.1.0/24)
```

### 3. Bring up the base stack

```bash
./scripts/bootstrap.sh               # tunes+exposes Ollama, applies firewall, builds model variants,
                                     # starts Docker services. Bundled Caddy is OFF by default.
```

### 4. Install the agent layer + pull models

```bash
cd agentic && ./scripts/setup-agentic.sh && cd ..
# pulls qwen3.6:27b (default), qwen3.6:35b-a3b, devstral:24b, gemma4:31b-it-qat; builds 64k variants;
# installs OpenCode configs to ~/.config/opencode/ so you can also run OpenCode ON the rig.
```

### 5. HTTPS for Open WebUI — pick ONE (see README "Add-on: HTTPS for Open WebUI")

- **You already run a reverse proxy (your NAS Caddy):** do nothing extra here. The bundled Caddy is
  profiled out, so it never starts. Add a block to your **NAS** Caddyfile:
  ```caddy
  ai.tabaska.us {
      reverse_proxy <rig-lan-ip>:3000
  }
  ```
  and set `WEBUI_URL=https://ai.tabaska.us` in `docker/.env`, then `cd docker && docker compose up -d`
  to apply. (For off-LAN access this name must also resolve over Tailscale — otherwise use one of the
  next two options from work.)
- **Let this box own HTTPS on your tailnet:** set `TS_HOSTNAME` in `.env`, enable MagicDNS + HTTPS
  Certificates in the Tailscale admin console, then `cd docker && docker compose --profile caddy up -d`.
- **No HTTPS, just Tailscale:** do nothing — browse `http://<rig>:3000` over Tailscale (encrypted on
  the wire; you only lose browser mic/clipboard/PWA features).

### 6. Allow Tailscale through the host firewall (only if you enabled ufw/firewalld in step 3)

```bash
sudo ufw allow in on tailscale0
# firewalld: sudo firewall-cmd --permanent --zone=trusted --add-interface=tailscale0 && sudo firewall-cmd --reload
```

### 7. Verify + get the rig's Tailscale name

```bash
./scripts/healthcheck.sh
tailscale status         # note the rig's name (e.g. "cachybox") — used on the Mac
```

---

## Phase 2 — On the work MacBook

### 1. Tailscale

```bash
brew install --cask tailscale     # or the Mac App Store app
tailscale up                       # SAME tailnet as the rig
tailscale status                   # confirm you can see the rig
```

Enable **MagicDNS** in the admin console so the short name `cachybox` resolves; otherwise use the full
`cachybox.tailnet-xxxx.ts.net` name or the `100.x.x.x` IP everywhere below.

### 2a. Open WebUI (chat) — zero install

Open a browser to whichever you set up in Phase 1 step 5:
`http://cachybox:3000`  •  or `https://ai.tabaska.us` (NAS proxy)  •  or `https://cachybox.tailnet-xxxx.ts.net` (bundled Caddy).
First account created becomes admin.

### 2b. OpenCode (agentic coding against the rig's models)

```bash
git clone git@github.com:btabaska/local-ai-tooling.git
cd local-ai-tooling/agentic && ./scripts/setup-agentic.sh
# on macOS this installs opencode/uv/repomix + configs; it auto-skips model pulls (no Ollama here)

$EDITOR ~/.config/opencode/opencode.json
#   change baseURL: "http://cachybox.local:11434/v1"  ->  "http://cachybox:11434/v1"

curl -s http://cachybox:11434/api/tags | head        # sanity: lists the rig's models?
cd ~/some-project && opencode                          # /models to confirm, then describe a feature
```

Only the LLM is remote — Serena, Context7, repomix, and the LSP run locally on the Mac against your
local checkout, so code intel is fast and files never leave the laptop except as prompts.

---

## Gotchas

- **`cachybox.local` vs `cachybox`:** `.local` is mDNS (same LAN only). From work always use the
  Tailscale MagicDNS name or the `100.x` IP — that's the one config edit that matters in 2b.
- **Bundled Caddy is opt-in.** `docker compose up -d` skips it. Only `--profile caddy up -d` starts it.
  No conflict with your NAS Caddy — they're on different hosts.
- **`code:opencode` / `gemma4-code:64k` handles live on the rig** (built in Phase 1). The Mac just
  references them by name over the API; nothing to build locally.
- **VRAM:** after a real task, `ollama ps` on the rig. If `qwen3.6:27b` @64k shows CPU offload, switch
  Build to `qwen3.6:35b-a3b` via `/models`, or lower context (see `agentic/README.md`).
