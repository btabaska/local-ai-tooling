#!/usr/bin/env python3
"""ldr-e2e.py — consumer-end probe for local-deep-research (lai-08).

Drives the WHOLE research chain, not liveness: logs into LDR as the dedicated
`ldr-probe` account (per-user SQLCipher DB; auto-re-registers after a volume
wipe), starts a real quick-mode research, and asserts it completes with a
cited report — which proves LDR -> LiteLLM (openai_endpoint, scoped virtual
key) -> llama-swap q38 AND LDR -> mini SearXNG all work.

Best-effort aware (mirrors journaling-loop-e2e): the strong model shares the
24GB card with Immich ML (night window) / games — before spending a research
run it pre-probes whether q38's upstream (llama-swap qwen3.8-27b)
can load AT ALL. If it can't, prints LDR_E2E_SKIP_GPU_BUSY (a PASS: VRAM
contention is policy, not an incident — see rig-gpu-vram-contention). The
pre-probe also warms the model so the research itself runs fast. A BAD is
only emitted when the model WAS loadable but the LDR pipeline still failed.

Run by verification check `ldr-research-e2e` (host: rig, tier: daily).
Prints exactly one LDR_E2E_* line; creds come from docker/.env (never argv).
"""
import json
import os
import re
import sys
import time
import http.cookiejar
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("LDR_URL", "http://localhost:5000")
LLAMA_SWAP = os.environ.get("LDR_LLAMA_URL", "http://localhost:9292")
# llama-swap upstream id behind the LiteLLM `q38` alias (LDR_LLM_MODEL).
# Keep in sync with docker/litellm-config.yaml if the alias is ever re-pointed.
STRONG_UPSTREAM = "qwen3.8-27b"
ENVF = os.path.expanduser("~/Documents/GitHub/local-ai-tooling/docker/.env")
QUERY = "What year was the Linux kernel first released and by whom?"
RESEARCH_BUDGET_S = 600


def bail(line):
    print(line)
    sys.exit(0)


env = {}
for raw in open(ENVF):
    raw = raw.strip()
    if raw and not raw.startswith("#") and "=" in raw:
        k, v = raw.split("=", 1)
        env[k] = v
user = env.get("LDR_PROBE_USER")
pw = env.get("LDR_PROBE_PASSWORD")
if not user or not pw:
    bail("LDR_E2E_BAD reason=probe-creds-missing-in-env")

# ── 1. best-effort gate: can the strong model load right now? ────────────────
try:
    body = json.dumps({"model": STRONG_UPSTREAM,
                       "messages": [{"role": "user", "content": "Say PONG"}],
                       "max_tokens": 8}).encode()
    r = urllib.request.urlopen(
        urllib.request.Request(LLAMA_SWAP + "/v1/chat/completions", data=body,
                               headers={"Content-Type": "application/json"}),
        timeout=240)
    if r.status != 200:
        bail("LDR_E2E_SKIP_GPU_BUSY http=%d" % r.status)
except Exception as e:  # OOM 500 / timeout / conn refused -> contention, not LDR
    bail("LDR_E2E_SKIP_GPU_BUSY err=%s" % type(e).__name__)

# ── 2. LDR session: login (register on a fresh volume) ───────────────────────
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(path, data=None, headers=None, form=False, timeout=60):
    h = dict(headers or {})
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
        else:
            body = json.dumps(data).encode()
            h["Content-Type"] = "application/json"
    try:
        r = op.open(urllib.request.Request(BASE + path, data=body, headers=h),
                    timeout=timeout)
        return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def form_csrf(path):
    _, html = call(path)
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    return m.group(1) if m else None


try:
    st, _ = call("/auth/login", {"username": user, "password": pw,
                                 "csrf_token": form_csrf("/auth/login")}, form=True)
    if st == 401:  # fresh ldr_data volume -> probe account gone; recreate it
        st, _ = call("/auth/register",
                     {"username": user, "password": pw, "confirm_password": pw,
                      "acknowledge": "true",
                      "csrf_token": form_csrf("/auth/register")}, form=True)
        if st != 200:
            bail("LDR_E2E_BAD reason=register-failed http=%d" % st)
    elif st != 200:
        bail("LDR_E2E_BAD reason=login-failed http=%d" % st)
    st, body = call("/auth/csrf-token")
    csrf = json.loads(body)["csrf_token"]
except Exception as e:
    bail("LDR_E2E_BAD reason=auth-flow err=%s" % type(e).__name__)

# ── 3. real research: quick mode, 1 iteration, SearXNG + q38 ────────
st, body = call("/api/start_research",
                {"query": QUERY, "mode": "quick", "model": "q38",
                 "model_provider": "OPENAI_ENDPOINT",
                 "search_engine": "searxng", "iterations": 1,
                 "questions_per_iteration": 1},
                headers={"X-CSRF-Token": csrf})
try:
    rid = json.loads(body).get("research_id")
except Exception:
    rid = None
if st != 200 or not rid:
    bail("LDR_E2E_BAD reason=start-research http=%d body=%.120s" % (st, body))

t0 = time.time()
status = "unknown"
while time.time() - t0 < RESEARCH_BUDGET_S:
    st, body = call("/api/research/%s/status" % rid)
    try:
        status = json.loads(body).get("status", "unknown")
    except Exception:
        status = "unparseable"
    if status in ("completed", "failed", "error", "suspended", "cancelled"):
        break
    time.sleep(10)
secs = int(time.time() - t0)
if status != "completed":
    bail("LDR_E2E_BAD reason=research-%s secs=%d" % (status, secs))

# ── 4. the consumer artifact: a cited report ─────────────────────────────────
st, body = call("/api/report/%s" % rid)
try:
    content = json.loads(body).get("content", "")
except Exception:
    content = ""
links = set(re.findall(r"https?://[^\s)\"'\]]+", content))
if st == 200 and len(content) > 500 and len(links) >= 3:
    bail("LDR_E2E_OK sources=%d chars=%d secs=%d" % (len(links), len(content), secs))
bail("LDR_E2E_BAD reason=report-thin http=%d chars=%d links=%d"
     % (st, len(content), len(links)))
