/**
 * memory.ts — DIY markdown agent-memory layer for opencode (homelab lai-18).
 *
 * WHY THIS EXISTS
 * opencode has no built-in memory (AGENTS.md is static, /init-only). This plugin
 * gives every project a durable, self-maintained MEMORY.md: when a session goes
 * idle or is about to be compacted, it reads the transcript via the plugin SDK
 * client (NEVER opencode.db / session files — issue #34445), asks a SMALL local
 * model (LiteLLM `utility`, 3B — GPU-safe, one call, no fan-out) to distill the
 * durable facts/decisions/gotchas, and APPENDS a dated, de-duplicated block to a
 * project-scoped markdown file. On each new turn it injects that memory back into
 * the system prompt, so the loop is closed: write on idle, read on start.
 *
 * DEPLOY: cp memory.ts ~/.config/opencode/plugins/  (auto-loaded; no registration)
 *
 * DESIGN RULES (do not "improve" away — they keep a single-GPU box safe):
 *   - ONE small-model call at a time (global single-flight); never parallel/background fan-out.
 *   - DEBOUNCE: a session is re-summarized at most once per window, and only when
 *     enough new messages exist — idle fires constantly.
 *   - SKIP trivial/empty sessions. SCRUB secrets before anything hits disk.
 *   - NEVER throw from a hook; memory is best-effort and must not disrupt a turn.
 */
import type { Plugin } from "@opencode-ai/plugin"
import { existsSync, mkdirSync, readFileSync, appendFileSync } from "node:fs"
import { homedir } from "node:os"
import { join, basename } from "node:path"

const DISABLED = process.env.OPENCODE_MEMORY_DISABLE === "1"
const MODEL = process.env.OPENCODE_MEMORY_MODEL || "utility"
const ENDPOINT = (process.env.OPENCODE_MEMORY_ENDPOINT || "https://llm.tabaska.us/v1").replace(/\/$/, "")
const API_KEY = process.env.LITELLM_API_KEY || ""
const MEM_DIR =
  process.env.OPENCODE_MEMORY_DIR ||
  join(process.env.XDG_DATA_HOME || join(homedir(), ".local", "share"), "opencode", "memory")

const DEBOUNCE_MS = 8 * 60_000 // don't re-summarize the same session more often than this
const MIN_NEW_MSGS = 2 // idle fires constantly; require at least a real exchange
const MIN_CHARS = 400 // skip trivial sessions
const MAX_SEND = 48_000 // cap transcript sent to the model (keep the tail)
const MAX_INJECT = 6_000 // cap memory injected back into the system prompt
const HTTP_MS = 60_000

const slug = (dir: string) => {
  let h = 5381
  for (let i = 0; i < dir.length; i++) h = ((h << 5) + h + dir.charCodeAt(i)) >>> 0
  return `${(basename(dir) || "root").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "root"}-${h.toString(36)}`
}
const memFile = (dir: string) => join(MEM_DIR, `${slug(dir)}.md`)

/** Redact anything that smells like a credential before it reaches disk. */
const scrub = (t: string) =>
  t
    .replace(/\beyJ[A-Za-z0-9._-]{20,}/g, "[redacted-jwt]")
    .replace(/\b(?:sk|pk|xoxb|ghp|gho|glpat)-[A-Za-z0-9._-]{8,}/g, "[redacted-key]")
    .replace(/\bBearer\s+[A-Za-z0-9._-]{8,}/gi, "Bearer [redacted]")
    .replace(/\b[A-Fa-f0-9]{40,}\b/g, "[redacted-hex]")
    .replace(/((?:pass(?:word|wd)?|secret|token|api[_-]?key|apikey)\s*[:=]\s*)(\S+)/gi, "$1[redacted]")

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()

export const Memory: Plugin = async ({ client, directory }) => {
  if (DISABLED || !API_KEY) return {}
  try { mkdirSync(MEM_DIR, { recursive: true }) } catch {}

  const lastAt = new Map<string, number>()
  const lastCount = new Map<string, number>()
  let inFlight = false

  const transcript = (list: any[]): { text: string; n: number } => {
    const lines: string[] = []
    for (const m of list) {
      const role = m?.info?.role
      if (role !== "user" && role !== "assistant") continue
      const txt = (m.parts || [])
        .filter((p: any) => p?.type === "text" && !p.synthetic && !p.ignored && p.text?.trim())
        .map((p: any) => p.text.trim())
        .join("\n")
      if (txt) lines.push(`${role === "user" ? "User" : "Assistant"}: ${txt}`)
    }
    let text = lines.join("\n\n")
    if (text.length > MAX_SEND) text = "…\n" + text.slice(-MAX_SEND)
    return { text, n: lines.length }
  }

  const summarize = async (sessionID: string, reason: string) => {
    if (inFlight || !sessionID) return
    const now = Date.now()
    // Global debounce: at most one summary per window per session, regardless of
    // trigger. Idle AND compaction both fire repeatedly; this bounds the model calls.
    if (now - (lastAt.get(sessionID) || 0) < DEBOUNCE_MS) return
    let raw: any
    try { raw = await client.session.messages({ path: { id: sessionID } }) } catch { return }
    const list = Array.isArray(raw) ? raw : raw?.data ?? []
    const { text, n } = transcript(list)
    if (text.length < MIN_CHARS) return
    if (reason === "idle" && n - (lastCount.get(sessionID) || 0) < MIN_NEW_MSGS) return

    inFlight = true
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), HTTP_MS)
      let content = ""
      try {
        const res = await fetch(`${ENDPOINT}/chat/completions`, {
          method: "POST",
          signal: ctrl.signal,
          headers: { "content-type": "application/json", authorization: `Bearer ${API_KEY}` },
          body: JSON.stringify({
            model: MODEL,
            temperature: 0.1,
            max_tokens: 400,
            messages: [
              {
                role: "system",
                content:
                  "You maintain a durable project-memory file for an autonomous coding agent. " +
                  "From the transcript extract ONLY durable, reusable facts: decisions, config " +
                  "values/paths/ports, gotchas, conventions, and how things work. EXCLUDE chit-chat, " +
                  "transient status, one-off commands, and anything obvious. Output a FLAT list of 0-6 " +
                  "terse bullets (NO headers, NO nesting, NO bold), each on its own line starting with " +
                  "'- ' and being one complete standalone fact (no pronouns referring to the chat). " +
                  "Never include secrets, tokens, passwords, or keys. If nothing durable is worth " +
                  "remembering, output exactly: NONE",
              },
              { role: "user", content: `Project: ${basename(directory)}\nTranscript (may be truncated):\n${text}` },
            ],
          }),
        })
        content = (await res.json())?.choices?.[0]?.message?.content?.trim() || ""
      } finally {
        clearTimeout(timer)
      }
      lastAt.set(sessionID, Date.now())
      lastCount.set(sessionID, n)
      if (!content || /^none\.?$/i.test(content)) return

      const bullets = scrub(content)
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => /^[-•*]\s+/.test(l))
        .map((l) => "- " + l.replace(/^[\s\-•*]+/, "").replace(/\*+$/, "").trim())
        .filter((l) => l.length > 2)
      if (!bullets.length) return

      const file = memFile(directory)
      const existing = existsSync(file) ? readFileSync(file, "utf8") : ""
      const seen = new Set(existing.split("\n").filter((l) => /^-\s+/.test(l)).map(norm))
      const fresh: string[] = []
      for (const b of bullets) {
        const k = norm(b)
        if (k.length < 6 || seen.has(k)) continue
        seen.add(k)
        fresh.push(b)
      }
      if (!fresh.length) return

      const stamp = new Date().toISOString().replace("T", " ").slice(0, 16)
      const header = existing ? "" : `# Project memory — ${basename(directory)}\n\n_Auto-maintained by the opencode memory plugin (lai-18). Durable facts only._\n`
      appendFileSync(file, `${header}\n## ${stamp} UTC (${reason})\n${fresh.join("\n")}\n`)
    } catch {
      /* best-effort */
    } finally {
      inFlight = false
    }
  }

  return {
    event: async ({ event }) => {
      // Await here: in `opencode run` the process exits right after idle, so a
      // fire-and-forget summary would be killed mid-flight. It is debounced +
      // single-flight + hard-timeout-bounded, so blocking this handler is cheap.
      if (event.type === "session.idle") await summarize((event as any).properties?.sessionID, "idle")
    },
    "experimental.session.compacting": async (input) => {
      void summarize(input.sessionID, "compacting")
    },
    // Read-back: inject the project's memory into the system prompt each turn.
    "experimental.chat.system.transform": async (_input, output) => {
      try {
        const file = memFile(directory)
        if (!existsSync(file)) return
        let mem = readFileSync(file, "utf8").trim()
        if (!mem) return
        if (mem.length > MAX_INJECT) mem = "…(older memory elided)…\n" + mem.slice(-MAX_INJECT)
        output.system.push(`<project-memory note="durable facts remembered from prior sessions">\n${mem}\n</project-memory>`)
      } catch {}
    },
  }
}
