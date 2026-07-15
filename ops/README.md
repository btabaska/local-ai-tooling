# ops/ — the homelab ops agent + skills library (ai-01)

Read-only fleet inspection exposed as MCP tools, consumable from three
surfaces. The **tools are the skills library**: add a new `@mcp.tool()` to
`fleet_mcp.py`, restart `fleet-mcp.service`, and every surface picks it up.

## Components

| File | What |
|---|---|
| `fleet_mcp.py` | FastMCP **streamable-http** server on rig `:8765/mcp`. READ-ONLY by construction: host enum (rig/mini/nas), unit-name regex, capped output, URL allowlist — there is deliberately no arbitrary-command tool. SSH via the `fleet-mini`/`fleet-nas` LAN entries (key `from=`-restricted on the remotes). |
| `fleet-mcp.service` | systemd unit (install: `sudo cp` → `daemon-reload` → `enable --now`). Env from `~/.config/fleet-mcp/env` (HEALTHCHECKS_API_KEY, LITELLM_API_KEY — values live in the foss-setup vault, never here). |
| `ops-agent.sh` | The **interactive ops agent**: ollmcp TUI → LiteLLM (`coder`) → fleet tools, **human-in-the-loop approval ON** (default). Run on the rig: `ssh rig -t '~/Documents/GitHub/local-ai-tooling/ops/ops-agent.sh'`. |
| `ops_probe.py` | Non-interactive one-shot agent loop (same tools). Used by the `rig-ops-agent-e2e` verification check and for scripted diagnoses. Safe headless because the toolset is read-only. |

## Surfaces

1. **ollmcp** (`ops-agent.sh`) — the human ops loop with per-call approvals.
2. **Open WebUI** — the same tools via mcpo (`http://mcpo:8000/fleet`,
   registered as the `fleet` external tool server). Ask the ops question in
   chat with the tool server enabled.
3. **ops_probe.py** — automation/CI (one question, bounded turns, exit code).

## Tools (v1)

`list_hosts`, `service_status(host,unit)`, `journal_tail(host,unit,lines)`,
`list_containers(host)`, `container_logs(host,container,lines)`,
`system_overview(host)`, `check_url(url)` (internal allowlist),
`run_verification_checks(host_filter)` (drives the mini harness),
`gpu_status()` (VRAM + loaded llama-swap models), `healthchecks_summary()`.

## Security posture

- Trusted-VLAN-only: rig UFW allows :8765 from 192.168.10.0/24 + the docker
  bridge pools only (NOT the tailnet).
- All tools read-only; mutations stay with humans.
- ollmcp HIL approval stays ON — do not `/hil` it off out of convenience.
- nas: the ssh user has no docker socket by design → container tools return
  a permission error there; use service/HTTP checks instead.

## Demonstrated 2026-07-15

Synthetic failed unit (`demo-broken.service`, missing config file):
`ops_probe.py "why is demo-broken down?"` → agent called `service_status` +
`journal_tail`, answered "Root cause: missing /etc/demo-broken/config.yaml"
with cited evidence, in 3.5 s on `coder` (qwen3.6-35b-a3b).
