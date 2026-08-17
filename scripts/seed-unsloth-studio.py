#!/usr/bin/env python3
"""seed-unsloth-studio.py — (re)apply the Unsloth Studio in-app wiring
(2026-08-17). Rebuild parity: Studio config is DB-only
(unsloth_studio_data volume, /workspace/studio/studio.db + auth/auth.db),
so a volume wipe erases connections/MCP/API keys — this script is their
canonical source, same contract as seed-owui-tool-servers.sh.

What it seeds (all idempotent):
  1. Provider "llama-swap (rig lanes)" — llama.cpp-compatible connection at
     http://llama-swap:8080/v1. ALL text models (chat, coder lanes,
     qwen3.8-27b, ...) serve through llama-swap with their tuned
     server-side params (qwen3.8-27b: ctx 98304, temp 1.0 / top-p 0.95 /
     top-k 20 / min-p 0, reasoning-effort medium — see
     docker/llama-swap-config.yaml). Studio must NOT load its own copy of
     these weights.
  2. Model scan folders /models/gguf (= /opt/llm/models RO) and
     /models/comfyui (= /opt/comfyui/models RO) so local GGUFs +
     diffusion checkpoints (Z-Image / FLUX / LTX families) are detectable
     without re-downloading.
  3. The four native-MCP servers OWUI chat also uses (mirror of
     seed-owui-tool-servers.sh — mcpo OpenAPI bridges are NOT MCP and
     cannot be wired here): fleet, comfyui (via arbiter-side container
     DNS), playwright, memos (bearer PAT via MEMOS_MCP_TOKEN env).
  4. A "verification" API key (sk-unsloth-…) if none exists — written to
     the path given by --key-out (mode 600, printed NEVER); store it at
     vault ai_stack.unsloth_api_key.

NOTE on auth: this Studio build IGNORES the UNSLOTH_STUDIO_PASSWORD
container env — first boot generates a diceware passphrase at
/workspace/studio/auth/.bootstrap_password (self-deletes on password
change). After a volume wipe: read that file, log in, change the password
to vault ai_stack.unsloth_studio_password, then run this script.

Run:  UNSLOTH_STUDIO_PASSWORD=<vault ai_stack.unsloth_studio_password> \
      MEMOS_MCP_TOKEN=<vault journaling.memos.mcp_token> \
      python3 scripts/seed-unsloth-studio.py [--key-out /path] \
          [--base http://localhost:8210]
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

PROVIDERS = [
    {
        "display_name": "llama-swap (rig lanes)",
        "base_url": "http://llama-swap:8080/v1",
        # "llama_cpp" is a HIDDEN registry type (absent from GET /api/providers/
        # registry — surfaced via the frontend's CUSTOM_PROVIDER_PRESETS) with
        # tool-calling+vision enabled and NO model-id allowlist. Do NOT use
        # "openai": its registry entry allowlists ^gpt-5.x/o3 ids, which
        # filters llama-swap's lanes to an empty picker. Candidates are probed
        # via POST /api/providers/models; first one returning models wins.
        "type_candidates": ["llama_cpp", "vllm", "openai"],
    },
]

SCAN_FOLDERS = ["/models/gguf", "/models/comfyui"]

MCP_SERVERS = [
    {
        "display_name": "Fleet (homelab inspection)",
        "url": "http://host.docker.internal:8765/mcp",
        "headers": None,
    },
    {
        "display_name": "ComfyUI (image gen, via arbiter)",
        "url": "http://comfyui-mcp:9000/mcp",
        "headers": None,
    },
    {
        "display_name": "Playwright browser",
        "url": "http://playwright-mcp:8931/mcp",
        "headers": None,
    },
    {
        "display_name": "Memos journal (mini)",
        "url": "http://192.168.10.2:5230/mcp",
        "headers": "MEMOS",  # replaced with bearer header from MEMOS_MCP_TOKEN
    },
]


class Api:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.token = None

    def call(self, method, path, data=None):
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(
            self.base + path,
            json.dumps(data).encode() if data is not None else None,
            headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("UNSLOTH_URL", "http://localhost:8210"))
    ap.add_argument("--key-out", help="write a newly-minted API key here (never printed)")
    args = ap.parse_args()

    pw = os.environ.get("UNSLOTH_STUDIO_PASSWORD")
    if not pw:
        sys.exit("UNSLOTH_STUDIO_PASSWORD not set (vault ai_stack.unsloth_studio_password)")

    api = Api(args.base)
    code, tok = api.call("POST", "/api/auth/login", {"username": "unsloth", "password": pw})
    if code != 200:
        sys.exit(f"login failed ({code}) — after a volume wipe, log in with "
                 f"auth/.bootstrap_password and change-password first (see header)")
    api.token = tok["access_token"]

    # 1. providers -----------------------------------------------------------
    code, existing = api.call("GET", "/api/providers/")
    existing = existing if isinstance(existing, list) else existing.get("providers", [])
    for want in PROVIDERS:
        ptype, ids = None, []
        for cand in want["type_candidates"]:
            code, models = api.call("POST", "/api/providers/models", {
                "provider_type": cand, "base_url": want["base_url"],
            })
            got = [m["id"] for m in models] if code == 200 and isinstance(models, list) else []
            if got:
                ptype, ids = cand, got
                break
            if code == 200 and ptype is None:
                ptype = cand  # known type, empty list — keep as fallback
        if not ptype:
            print(f"SKIP provider {want['display_name']}: no candidate type accepted")
            continue
        current = next((p for p in existing if p.get("base_url") == want["base_url"]), None)
        if current and current.get("provider_type") != ptype:
            code, _ = api.call("DELETE", f"/api/providers/{current['id']}")
            print(f"ok provider re-type: deleted stale {current['provider_type']} entry ({code})")
            current = None
        if current:
            print(f"ok provider (exists): {want['display_name']} [{ptype}]")
        else:
            code, r = api.call("POST", "/api/providers/", {
                "provider_type": ptype,
                "display_name": want["display_name"],
                "base_url": want["base_url"],
            })
            print(f"{'ok' if code in (200, 201) else 'FAIL'} provider create "
                  f"{want['display_name']} [{ptype}]: {code}"
                  f"{' ' + json.dumps(r)[:120] if code not in (200, 201) else ''}")
        print(f"   models via {want['display_name']}: {len(ids)} "
              f"(qwen3.8-27b {'PRESENT' if 'qwen3.8-27b' in ids else 'MISSING'})")

    # 2. scan folders --------------------------------------------------------
    code, sf = api.call("GET", "/api/models/scan-folders")
    have = {f["path"] for f in (sf if isinstance(sf, list) else sf.get("folders", []))}
    for path in SCAN_FOLDERS:
        if path in have:
            print(f"ok scan-folder (exists): {path}")
            continue
        code, r = api.call("POST", "/api/models/scan-folders", {"path": path})
        print(f"{'ok' if code in (200, 201) else 'FAIL'} scan-folder {path}: {code}"
              f"{' ' + json.dumps(r)[:120] if code not in (200, 201) else ''}")

    # 3. MCP servers ---------------------------------------------------------
    memos_token = os.environ.get("MEMOS_MCP_TOKEN", "")
    code, servers = api.call("GET", "/api/mcp/servers/")
    servers = servers if isinstance(servers, list) else servers.get("servers", [])
    have_urls = {s.get("url") for s in servers}
    for want in MCP_SERVERS:
        headers = want["headers"]
        if headers == "MEMOS":
            if not memos_token:
                print(f"SKIP mcp {want['display_name']}: MEMOS_MCP_TOKEN not set")
                continue
            headers = {"Authorization": f"Bearer {memos_token}"}
        if want["url"] in have_urls:
            print(f"ok mcp (exists): {want['display_name']}")
            continue
        code, probe = api.call("POST", "/api/mcp/servers/test", {
            "url": want["url"], "headers": headers,
        })
        if not (code == 200 and probe.get("ok")):
            print(f"WARN mcp {want['display_name']} probe failed "
                  f"({code} {json.dumps(probe)[:120]}) — adding anyway (may be model-gated)")
        code, r = api.call("POST", "/api/mcp/servers/", {
            "display_name": want["display_name"], "url": want["url"],
            "headers": headers, "is_enabled": True, "use_oauth": False,
        })
        tools = probe.get("tool_count", "?")
        print(f"{'ok' if code in (200, 201) else 'FAIL'} mcp {want['display_name']}: "
              f"{code} tools={tools}{' ' + json.dumps(r)[:120] if code not in (200, 201) else ''}")

    # 4. API key -------------------------------------------------------------
    code, keys = api.call("GET", "/api/auth/api-keys")
    names = [k["name"] for k in keys.get("api_keys", [])]
    if "verification" in names:
        print("ok api-key (exists): verification")
    elif not args.key_out:
        print("SKIP api-key mint: no --key-out given")
    else:
        code, r = api.call("POST", "/api/auth/api-keys", {"name": "verification"})
        if code in (200, 201):
            fd = os.open(args.key_out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(r["key"])
            print(f"ok api-key minted: verification -> {args.key_out} "
                  "(store at vault ai_stack.unsloth_api_key)")
        else:
            print(f"FAIL api-key mint: {code} {json.dumps(r)[:120]}")

    print("seed complete")


if __name__ == "__main__":
    main()
