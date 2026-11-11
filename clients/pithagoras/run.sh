#!/bin/bash
# Pithagoras portal (native, Mac) — launched by ~/Library/LaunchAgents/us.tabaska.pithagoras.plist
# pi = the portal's bundled 1.1.x CLI with an isolated agent dir (models/auth/mcp.json),
# so the global ~/.pi/agent (pi 0.82) is untouched. Default model: litellm/strata.
set -euo pipefail
export PATH="/Users/brandontabaska/GitHub/pithagoras/node_modules/.bin:/opt/homebrew/opt/node@24/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PI_CODING_AGENT_DIR="/Users/brandontabaska/.local/share/pithagoras/pi-agent"
export DATA_DIR="/Users/brandontabaska/.local/share/pithagoras/data" SESSION_DIR="/Users/brandontabaska/.local/share/pithagoras/sessions"
export WORKSPACE_ROOT="/Users/brandontabaska/RE"
export PORT=4100 TZ=America/New_York PORTAL_UPDATE_RESTART=exit
export GHIDRA_INSTALL_DIR="/Users/brandontabaska/.local/opt/ghidra_12.1.4_PUBLIC"
export JAVA_HOME="/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home"
set -a; . "/Users/brandontabaska/.local/share/pithagoras/secret.env"; set +a
cd "/Users/brandontabaska/GitHub/pithagoras"
exec node core/server/dist/index.js
