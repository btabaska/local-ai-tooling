#!/usr/bin/env python3
"""fleet-mcp — READ-ONLY homelab fleet-inspection tools over MCP (ai-01).

Serves streamable-http MCP at http://<rig>:8765/mcp for:
  - ollmcp (the interactive ops agent, human-in-the-loop approvals)
  - mcpo   (bridges it to OpenAPI for Open WebUI tools)
  - ops_probe.py (non-interactive ops-agent liveness / demo driver)

SAFETY MODEL: every tool builds its command from validated, constrained
arguments (host enum, unit-name regex, capped line counts, URL allowlist).
There is deliberately NO arbitrary-command tool — the LLM cannot inject.
SSH to mini/nas uses the dedicated `fleet-*` LAN entries (key restricted by
from= on the remote side). Keep this server Trusted-VLAN-only (rig UFW).

Deployed as fleet-mcp.service (systemd, see ops/fleet-mcp.service).
"""
import re
import subprocess
import json
import os
import time
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fleet", host="0.0.0.0", port=8765)

HOSTS = {
    "rig": {
        "ssh": None,
        "desc": "CachyOS gaming/AI box, 192.168.10.12. Runs the AI stack "
                "(llama-swap :9292, LiteLLM :4000, Open WebUI :3000, mcpo :8000, "
                "ollama shim :11434), game servers (AMP, Palworld) and Apollo "
                "game streaming. 24/7.",
    },
    "mini": {
        "ssh": "fleet-mini",
        "desc": "Mac mini (Debian), 192.168.10.2. Caddy reverse proxy for "
                "*.tabaska.us, DNS, the verification harness (/opt/verification), "
                "Uptime-Kuma, Forgejo. 24/7.",
    },
    "nas": {
        "ssh": "fleet-nas",
        "desc": "Synology NAS, 192.168.10.4. Media stack (*arr, Plex, CWA), "
                "backups (Hyper Backup->B2). NOTE: this tool's restricted "
                "credentials cannot query docker on the nas — a failed container "
                "listing there is a TOOL limitation, not evidence about the host "
                "(containers may be running fine). Use service/HTTP checks instead.",
    },
}

UNIT_RE = re.compile(r"^[A-Za-z0-9@:._-]{1,80}$")
URL_ALLOW = re.compile(
    r"^https?://("
    r"[a-z0-9.-]+\.tabaska\.us|[a-z0-9.-]+\.ts\.net|"
    r"192\.168\.\d{1,3}\.\d{1,3}|127\.0\.0\.1|localhost|100\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r")(:\d{1,5})?(/.*)?$"
)


def _run(host: str, remote_cmd: str, timeout: int = 30) -> str:
    """Run a pre-validated read-only command locally (rig) or over ssh."""
    if host not in HOSTS:
        return f"ERROR: unknown host {host!r}; known: {list(HOSTS)}"
    alias = HOSTS[host]["ssh"]
    if alias:
        argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", alias, remote_cmd]
    else:
        argv = ["bash", "-c", remote_cmd]
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout + p.stderr).strip()
        return out[:6000] if out else f"(no output, exit {p.returncode})"
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {timeout}s"


@mcp.tool()
def list_hosts() -> str:
    """List the homelab hosts this agent can inspect, with their roles."""
    return "\n".join(f"{k}: {v['desc']}" for k, v in HOSTS.items())


@mcp.tool()
def service_status(host: str, unit: str) -> str:
    """systemctl status for one unit on a host (rig|mini|nas). Read-only."""
    if not UNIT_RE.match(unit):
        return "ERROR: unit name contains characters this tool refuses (input validation) - this says NOTHING about whether the unit exists"
    return _run(host, f"systemctl status {unit} --no-pager -l -n 0 2>&1; "
                      f"echo; echo 'is-active:' $(systemctl is-active {unit} 2>&1)")


@mcp.tool()
def journal_tail(host: str, unit: str, lines: int = 100) -> str:
    """Last N journal lines for a unit on a host (max 300). Read-only."""
    if not UNIT_RE.match(unit):
        return "ERROR: unit name contains characters this tool refuses (input validation) - this says NOTHING about whether the unit exists"
    lines = max(1, min(int(lines), 300))
    return _run(host, f"journalctl -u {unit} -n {lines} --no-pager 2>&1")


@mcp.tool()
def list_containers(host: str) -> str:
    """Docker containers on a host with status. On nas this tool lacks docker
    access — a failure there is a tool limitation, not evidence about the host."""
    return _run(host, "docker ps -a --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}' 2>&1")


@mcp.tool()
def container_logs(host: str, container: str, lines: int = 100) -> str:
    """Last N log lines of a docker container (max 300)."""
    if not UNIT_RE.match(container):
        return "ERROR: container name contains characters this tool refuses (input validation)"
    lines = max(1, min(int(lines), 300))
    return _run(host, f"docker logs --tail {lines} {container} 2>&1")


@mcp.tool()
def system_overview(host: str) -> str:
    """Uptime, memory, disk and load for a host."""
    return _run(host, "uptime; echo; free -h 2>/dev/null | head -2; echo; df -h / /volume1 2>/dev/null | head -5")


@mcp.tool()
def check_url(url: str) -> str:
    """HTTP status + latency for an internal URL (tabaska.us / ts.net / LAN only).
    Redirects are followed and reported — a '302 login redirect' service shows as
    'HTTP 200 (followed redirect ...)', which usually means alive, not broken."""
    if not URL_ALLOW.match(url):
        return "ERROR: URL not in the internal allowlist"
    t0 = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.status
            body = r.read(200)
            final = r.geturl()
        note = f" (followed redirect -> {final})" if final.rstrip("/") != url.rstrip("/") else ""
        return f"HTTP {code}{note} in {(time.time()-t0)*1000:.0f} ms; first bytes: {body[:120]!r}"
    except Exception as e:
        return f"ERROR after {(time.time()-t0)*1000:.0f} ms: {type(e).__name__}: {e}"


@mcp.tool()
def search_web(query: str, max_results: int = 8) -> str:
    """Web search via the homelab's own SearXNG metasearch (searxng.tabaska.us).
    Use for anything about software versions, upstream APIs/behavior, error messages,
    or current events you are not certain of. Returns title, URL and snippet per hit."""
    if not query or len(query) > 300:
        return "TOOL-ERROR: query must be 1-300 characters"
    max_results = max(1, min(int(max_results), 15))
    q = urllib.parse.urlencode({"q": query, "format": "json"})
    try:
        with urllib.request.urlopen(f"https://searxng.tabaska.us/search?{q}", timeout=15) as r:
            data = json.load(r)
    except Exception as e:
        return (f"TOOL-ERROR: SearXNG unreachable ({type(e).__name__}: {e}) — "
                f"a search-stack problem, not evidence about your question")
    results = data.get("results", [])[:max_results]
    if not results:
        return f"0 results for {query!r} (SearXNG reachable; try different terms)"
    lines = [f"{len(results)} results for {query!r}:"]
    for i, res in enumerate(results, 1):
        snippet = (res.get("content") or "").replace("\n", " ")[:200]
        lines.append(f"{i}. {res.get('title','')[:100]}\n   {res.get('url','')}\n   {snippet}")
    return "\n".join(lines)


@mcp.tool()
def run_verification_checks(host_filter: str) -> str:
    """Run the homelab verification harness (on mini) for one host tier:
    rig|mini|nas|url|ha... Returns the checks report. Takes up to 2 minutes."""
    if not re.match(r"^[a-z0-9-]{1,20}$", host_filter):
        return "ERROR: invalid host filter"
    return _run("mini", f"cd /opt/verification && ./bin/checks_runner.py --host {host_filter} 2>&1", timeout=150)


@mcp.tool()
def gpu_status() -> str:
    """Rig GPU: VRAM/util + which LLM models are currently loaded (llama-swap)."""
    smi = _run("rig", "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader")
    try:
        used, total, util, temp = [f.strip().split(" ")[0] for f in smi.strip().split(",")]
        gpu_line = (f"vram_used={used} MiB, vram_total={total} MiB, "
                    f"gpu_util={util} %, gpu_temp={temp} C")
    except ValueError:
        gpu_line = smi  # unexpected smi output — pass through raw
    try:
        with urllib.request.urlopen("http://localhost:9292/running", timeout=5) as r:
            running = json.load(r).get("running", [])
        models = ", ".join(f"{m['model']}({m['state']})" for m in running) or "(none loaded)"
    except Exception as e:
        models = f"llama-swap unreachable: {e}"
    return f"GPU: {gpu_line}\nLoaded models: {models}"


@mcp.tool()
def healthchecks_summary() -> str:
    """Self-hosted Healthchecks (health.tabaska.us) dead-man switches: list any
    check that is not up."""
    key = os.environ.get("HEALTHCHECKS_API_KEY", "")
    if not key:
        return ("TOOL-ERROR: HEALTHCHECKS_API_KEY not configured in fleet-mcp — "
                "this says nothing about actual check states")
    req = urllib.request.Request("https://health.tabaska.us/api/v3/checks/",
                                 headers={"X-Api-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            checks = json.load(r)["checks"]
    except Exception as e:
        return (f"TOOL-ERROR: fleet-mcp could not query the Healthchecks API "
                f"({type(e).__name__}: {e}) — a credential/connectivity problem "
                f"of this tool, not evidence that homelab checks are failing")
    bad = [c for c in checks if c.get("status") not in ("up", "paused")]
    lines = [f"{len(checks)} checks; {len(bad)} not-up"]
    for c in bad:
        lines.append(f"  {c['name']}: {c['status']} (last ping {c.get('last_ping','?')})")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
