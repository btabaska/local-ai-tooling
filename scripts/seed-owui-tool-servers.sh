#!/bin/bash
# seed-owui-tool-servers.sh — (re)apply Open WebUI's External Tool server
# connections (lai-04, 2026-08-05; extended lai-11, 2026-08-06). Rebuild parity:
# these connections are PersistentConfig — they live ONLY in the open_webui_data
# volume DB (config key tool_server.connections), so a volume wipe silently
# erases them. This script is their canonical source.
#
# Topology (lai-04 + lai-11):
# - NATIVE MCP (streamable-HTTP, OWUI >=0.6.31; type "mcp"):
#     fleet      -> http://host.docker.internal:8765/mcp (fleet-mcp.service on
#                   the rig host, ops/fleet-mcp.service). Function filter keeps
#                   9 of 10 tools — run_verification_checks is excluded
#                   (minutes-long full check sweep; chat-hostile).
#     context7   -> https://mcp.context7.com/mcp (hosted, keyless, low rate).
#     comfyui    -> http://comfyui-mcp:9000/mcp (lai-11; docker/comfyui-mcp).
#                   Filter keeps 3 of 17: the two curated workflow tools
#                   (zimage_turbo, noobai_anime) + view_image. Job/asset/publish
#                   plumbing stays opencode-only.
#     playwright -> http://playwright-mcp:8931/mcp (lai-11; microsoft/playwright-mcp,
#                   headless chromium, --isolated). Filter keeps 8 of 24 chat-shaped
#                   browse tools; evaluate/run_code_unsafe/network stay opencode-only.
# - mcpo (OpenAPI bridge, stdio-only servers stay here):
#     time / fetch / serena / sequential-thinking.
#   serena is FILTERED to 9 of 21 (lai-11; lai-16 dropped tool_onboarding): read-only code intel + memory reads.
#   NOTE mcpo tool names in OWUI are the OpenAPI operationIds (tool_<name>_post),
#   so the openapi filter entries below use that full form; native-mcp filters
#   use bare tool names.
#   The 12 cut tools are all mutating (replace_*/insert_*/rename_*/delete_*/
#   *_memory writes) — OWUI chat is a read-only consumer; opencode keeps full
#   serena via its own MCP client.
#   mcpo ALSO still serves /fleet and /context7 passthroughs for non-OWUI
#   consumers (mcpo-config.json unchanged) — OWUI just no longer uses them.
#   openzim (lai-13): openzim-mcp v2.5.5 advanced mode (8 tools) over the NAS
#   ZIM library (rig /mnt/nas-zim RO CIFS -> /zim in the mcpo container).
#   Filtered to 3 of 8 chat-shaped tools: zim_query (the NL intelligent tool,
#   best router for small models) + zim_search + zim_get. browse/links/
#   metadata/get_section/health stay opencode-only (opencode spawns its own
#   stdio openzim-mcp on the rig — full advanced set).
#
#   memos (journal-09, 2026-08-17): the Memos BUILT-IN MCP server on the mini
#   (http://192.168.10.2:5230/mcp, in Memos since 0.27 — no extra container).
#   Bearer auth with a DEDICATED PAT (vault journaling.memos.mcp_token, NOT
#   n8n's api_token) injected at run time via $MEMOS_MCP_TOKEN — the
#   __MEMOS_MCP_TOKEN__ placeholder below keeps the secret out of git.
#   Filtered to 2 of 19: search_memos (journal recall) + create_memo (capture).
#   The other 17 (update/delete/comments/attachments/reactions/relations/tags)
#   stay out of chat — destructive ops don't belong in a small-model tool belt,
#   and the budget is at cap. opencode gets the same 2-tool posture via
#   clients/opencode.json (memos remote MCP, {env:MEMOS_MCP_TOKEN}).
#
# Tool budget: fleet 9 + context7 2 + serena 9 + time 2 + fetch 1 +
# sequential-thinking 1 + comfyui 3 + playwright 8 + openzim 3 + memos 2 = 40
# OWUI-visible tools (AT the ~40 cap that degrades small-model routing — the
# next addition must trade something out; the
# lai-16 notes-MCP read pair retired 2026-08-14 with the read-27 trial). Guarded by the mini checks
# `owui-mcp-tools` (budget) + `image-browser-mcp` (lai-11 servers + filters).
#
# NOTE: chat models reference these by stable ids (server:time, server:fetch,
# server:serena, server:sequential-thinking, server:mcp:fleet,
# server:mcp:context7, server:mcp:comfyui, server:mcp:playwright,
# server:openzim, server:mcp:memos) in
# model.meta.toolIds — keep info.id values stable.
#
# NOTE filter semantics: OWUI matches with is_string_allowed = name ENDSWITH
# entry (allow-list) — every entry below was checked against sibling tool names
# for suffix collisions before landing here; re-check when adding entries.
#
# Run ON rig:  OWUI_API_KEY=<admin api key> MEMOS_MCP_TOKEN=<memos PAT> \
#              bash scripts/seed-owui-tool-servers.sh
# Key source:  foss-setup vault ai_stack.openwebui_rag_sync_api_key (admin) +
#              journaling.memos.mcp_token (memos MCP PAT).
# Idempotent:  full-list replace of tool_server.connections (this IS the list).
set -euo pipefail

BASE="${OWUI_URL:-http://localhost:3000}"
[ -n "${OWUI_API_KEY:-}" ] || { echo "OWUI_API_KEY not set (vault ai_stack.openwebui_rag_sync_api_key)" >&2; exit 1; }
[ -n "${MEMOS_MCP_TOKEN:-}" ] || { echo "MEMOS_MCP_TOKEN not set (vault journaling.memos.mcp_token)" >&2; exit 1; }

payload=$(cat <<'JSON'
{"TOOL_SERVER_CONNECTIONS": [
 {"url": "http://mcpo:8000/time", "path": "openapi.json", "type": "openapi", "auth_type": "bearer", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "", "access_grants": []},
  "info": {"id": "time", "name": "time", "description": "mcpo stdio bridge: mcp-server-time"}, "spec_type": "url", "spec": ""},
 {"url": "http://mcpo:8000/fetch", "path": "openapi.json", "type": "openapi", "auth_type": "bearer", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "", "access_grants": []},
  "info": {"id": "fetch", "name": "fetch", "description": "mcpo stdio bridge: mcp-server-fetch"}, "spec_type": "url", "spec": ""},
 {"url": "http://mcpo:8000/serena", "path": "openapi.json", "type": "openapi", "auth_type": "bearer", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "tool_get_symbols_overview_post,tool_find_symbol_post,tool_find_referencing_symbols_post,tool_find_implementations_post,tool_find_declaration_post,tool_get_diagnostics_for_file_post,tool_read_memory_post,tool_list_memories_post,tool_initial_instructions_post", "access_grants": []},
  "info": {"id": "serena", "name": "serena", "description": "mcpo stdio bridge: semantic code intel (project /repos/app). Filtered to 9 read-only tools (lai-11; tool_onboarding, which writes memories, dropped in lai-16); editing tools are opencode-only."}, "spec_type": "url", "spec": ""},
 {"url": "http://mcpo:8000/openzim", "path": "openapi.json", "type": "openapi", "auth_type": "bearer", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "tool_zim_query_post,tool_zim_search_post,tool_zim_get_post", "access_grants": []},
  "info": {"id": "openzim", "name": "openzim", "description": "mcpo stdio bridge: openzim-mcp v2.5.5 over the NAS ZIM library (RO, /mnt/nas-zim). Filtered to 3 of 8 (lai-13): zim_query (NL) + zim_search + zim_get; browse/links/metadata/section/health are opencode-only."}, "spec_type": "url", "spec": ""},
 {"url": "http://mcpo:8000/sequential-thinking", "path": "openapi.json", "type": "openapi", "auth_type": "bearer", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "", "access_grants": []},
  "info": {"id": "sequential-thinking", "name": "sequential thinking", "description": "mcpo stdio bridge: reasoning scratchpad"}, "spec_type": "url", "spec": ""},
 {"url": "http://host.docker.internal:8765/mcp", "path": "", "type": "mcp", "auth_type": "none", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "list_hosts,service_status,journal_tail,list_containers,container_logs,system_overview,check_url,gpu_status,healthchecks_summary", "access_grants": []},
  "info": {"id": "fleet", "name": "Fleet (native MCP)", "description": "Read-only homelab fleet inspection (ai-01, fleet-mcp.service on the rig) over native streamable-HTTP. run_verification_checks is filtered out (minutes-long, chat-hostile)."}},
 {"url": "https://mcp.context7.com/mcp", "path": "", "type": "mcp", "auth_type": "none", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "", "access_grants": []},
  "info": {"id": "context7", "name": "Context7 (native MCP)", "description": "Up-to-date library docs — hosted streamable-HTTP endpoint, keyless (low rate)."}},
 {"url": "http://comfyui-mcp:9000/mcp", "path": "", "type": "mcp", "auth_type": "none", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "zimage_turbo,noobai_anime,view_image", "access_grants": []},
  "info": {"id": "comfyui", "name": "ComfyUI (native MCP)", "description": "Image generation tools (lai-11, comfyui-mcp v1.1.1 -> gpu-arbiter): zimage_turbo (realistic, 8-step) + noobai_anime (SDXL anime) + view_image. Full 17-tool set is opencode-only."}},
 {"url": "http://playwright-mcp:8931/mcp", "path": "", "type": "mcp", "auth_type": "none", "headers": null, "key": "",
  "config": {"enable": true, "function_name_filter_list": "browser_navigate,browser_navigate_back,browser_snapshot,browser_take_screenshot,browser_click,browser_type,browser_fill_form,browser_wait_for", "access_grants": []},
  "info": {"id": "playwright", "name": "Playwright browser (native MCP)", "description": "Headless-chromium browsing (lai-11, microsoft/playwright-mcp v0.0.79, --isolated): navigate/snapshot/screenshot/interact. evaluate + network tools are opencode-only."}},
 {"url": "http://192.168.10.2:5230/mcp", "path": "", "type": "mcp", "auth_type": "bearer", "headers": null, "key": "__MEMOS_MCP_TOKEN__",
  "config": {"enable": true, "function_name_filter_list": "search_memos,create_memo", "access_grants": []},
  "info": {"id": "memos", "name": "Memos journal (native MCP)", "description": "The journal on the mini — Memos' BUILT-IN MCP server (journal-09). Filtered to 2 of 19: search_memos (recall past entries) + create_memo (capture a note). Bearer PAT = vault journaling.memos.mcp_token; update/delete/comment tools stay out of chat by policy."}}
]}
JSON
)
payload=${payload//__MEMOS_MCP_TOKEN__/$MEMOS_MCP_TOKEN}

curl -sf -m 120 -X POST -H "Authorization: Bearer $OWUI_API_KEY" -H 'Content-Type: application/json' \
  --data-binary "$payload" "$BASE/api/v1/configs/tool_servers" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); [print(c["type"], (c.get("info") or {}).get("id"), c["url"]) for c in d["TOOL_SERVER_CONNECTIONS"]]'
echo "OK: tool server connections applied."
