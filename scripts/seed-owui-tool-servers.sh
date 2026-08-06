#!/bin/bash
# seed-owui-tool-servers.sh — (re)apply Open WebUI's External Tool server
# connections (lai-04, 2026-08-05). Rebuild parity: these connections are
# PersistentConfig — they live ONLY in the open_webui_data volume DB
# (config key tool_server.connections), so a volume wipe silently erases
# them. This script is their canonical source.
#
# Topology (lai-04):
# - NATIVE MCP (streamable-HTTP, OWUI >=0.6.31; type "mcp"):
#     fleet    -> http://host.docker.internal:8765/mcp (fleet-mcp.service on
#                 the rig host, ops/fleet-mcp.service). Function filter keeps
#                 9 of 10 tools — run_verification_checks is excluded
#                 (minutes-long full check sweep; chat-hostile).
#     context7 -> https://mcp.context7.com/mcp (hosted, keyless, low rate).
# - mcpo (OpenAPI bridge, stdio-only servers stay here):
#     time / fetch / serena / sequential-thinking.
#   mcpo ALSO still serves /fleet and /context7 passthroughs for non-OWUI
#   consumers (mcpo-config.json unchanged) — OWUI just no longer uses them.
#
# Tool budget: fleet 9 + context7 2 + serena 21 + time 2 + fetch 1 +
# sequential-thinking 1 = 36 OWUI-visible tools (< the ~40 cap that degrades
# small-model routing). Guarded by the mini check `owui-mcp-tools`.
#
# NOTE: chat models reference these by stable ids (server:time, server:fetch,
# server:serena, server:sequential-thinking, server:mcp:fleet,
# server:mcp:context7) in model.meta.toolIds — keep info.id values stable.
#
# Run ON rig:  OWUI_API_KEY=<admin api key> bash scripts/seed-owui-tool-servers.sh
# Key source:  foss-setup vault ai_stack.openwebui_rag_sync_api_key (admin).
# Idempotent:  full-list replace of tool_server.connections (this IS the list).
set -euo pipefail

BASE="${OWUI_URL:-http://localhost:3000}"
[ -n "${OWUI_API_KEY:-}" ] || { echo "OWUI_API_KEY not set (vault ai_stack.openwebui_rag_sync_api_key)" >&2; exit 1; }

payload=$(cat <<'JSON'
{"TOOL_SERVER_CONNECTIONS": [
 {"url": "http://mcpo:8000/time", "path": "openapi.json", "type": "openapi", "auth_type": "bearer", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "", "access_grants": []},
  "info": {"id": "time", "name": "time", "description": "mcpo stdio bridge: mcp-server-time"}, "spec_type": "url", "spec": ""},
 {"url": "http://mcpo:8000/fetch", "path": "openapi.json", "type": "openapi", "auth_type": "bearer", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "", "access_grants": []},
  "info": {"id": "fetch", "name": "fetch", "description": "mcpo stdio bridge: mcp-server-fetch"}, "spec_type": "url", "spec": ""},
 {"url": "http://mcpo:8000/serena", "path": "openapi.json", "type": "openapi", "auth_type": "bearer", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "", "access_grants": []},
  "info": {"id": "serena", "name": "serena", "description": "mcpo stdio bridge: semantic code intel (project /repos/app)"}, "spec_type": "url", "spec": ""},
 {"url": "http://mcpo:8000/sequential-thinking", "path": "openapi.json", "type": "openapi", "auth_type": "bearer", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "", "access_grants": []},
  "info": {"id": "sequential-thinking", "name": "sequential thinking", "description": "mcpo stdio bridge: reasoning scratchpad"}, "spec_type": "url", "spec": ""},
 {"url": "http://host.docker.internal:8765/mcp", "path": "", "type": "mcp", "auth_type": "none", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "list_hosts,service_status,journal_tail,list_containers,container_logs,system_overview,check_url,gpu_status,healthchecks_summary", "access_grants": []},
  "info": {"id": "fleet", "name": "Fleet (native MCP)", "description": "Read-only homelab fleet inspection (ai-01, fleet-mcp.service on the rig) over native streamable-HTTP. run_verification_checks is filtered out (minutes-long, chat-hostile)."}},
 {"url": "https://mcp.context7.com/mcp", "path": "", "type": "mcp", "auth_type": "none", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "", "access_grants": []},
  "info": {"id": "context7", "name": "Context7 (native MCP)", "description": "Up-to-date library docs — hosted streamable-HTTP endpoint, keyless (low rate)."}}
]}
JSON
)

curl -sf -m 120 -X POST -H "Authorization: Bearer $OWUI_API_KEY" -H 'Content-Type: application/json' \
  --data-binary "$payload" "$BASE/api/v1/configs/tool_servers" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); [print(c["type"], (c.get("info") or {}).get("id"), c["url"]) for c in d["TOOL_SERVER_CONNECTIONS"]]'
echo "OK: tool server connections applied."
