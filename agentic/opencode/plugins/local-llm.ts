/**
 * local-llm.ts — deterministic verification loop for local-model coding agents.
 *
 * WHY THIS EXISTS
 * With a 35B local model instead of a frontier model, *forcing* verification beats
 * *prompting* for correctness. This plugin closes the two Claude Code features that
 * matter most when the model is weak:
 *
 *   1. PostToolUse  -> `tool.execute.after` runs a fast verify command after every
 *                      edit/write and appends failures straight into the tool result
 *                      the model reads. The model cannot "forget" to check its work.
 *   2. Stop         -> `event: session.idle` re-runs verification when the agent
 *                      thinks it is done, and pushes it back to work if it is not.
 *   3. Tool budget  -> `tool.definition` trims bloated MCP tool descriptions before
 *                      they reach the model (stock serena alone is ~8.8k tokens of
 *                      schema; tool-selection accuracy degrades past ~30 tools).
 *
 * DEPLOY
 *   cp agentic/opencode/plugins/local-llm.ts ~/.config/opencode/plugins/
 * (or .opencode/plugins/ for a single project). Auto-loaded at startup; no config
 * registration needed. Runs on both the rig (CachyOS) and macOS — it shells out only
 * to binaries it has verified are resolvable.
 *
 * VERIFY COMMAND RESOLUTION (first match wins, all optional):
 *   1. $OPENCODE_VERIFY_CMD          — explicit override, always respected
 *   2. .opencode/verify.sh           — per-repo escape hatch
 *   3. `just verify-fast`            — if a justfile declares that recipe
 *   4. auto-detected ruff / tsc      — ONLY if the binary actually resolves
 *   5. none                          — plugin disables itself silently
 *
 * Design rules that matter for a small model (do not "improve" these away):
 *   - SILENT ON PASS. Success output is pure context tax; emit nothing.
 *   - HARD TRUNCATION. A 500-line tsc dump evicts the model's working memory.
 *   - DEBOUNCE. Multi-file refactors fire edit-after-edit; don't run 30 typechecks.
 *   - HARD TIMEOUT. A hung verify must never hang an agent turn.
 *   - ONE COMMAND NAME. Don't make the model learn a matrix of verify invocations.
 */
import type { Plugin } from "@opencode-ai/plugin"
import { existsSync, readFileSync } from "node:fs"
import { join } from "node:path"

const EDIT_TOOLS = new Set(["edit", "write", "patch", "multiedit"])
const DEBOUNCE_MS = 4_000
const TIMEOUT_MS = 45_000
const MAX_LINES = 40
const MAX_CHARS = 4_000
/** Max times a single session may be pushed back to work before we give up. */
const MAX_NUDGES = 2
/** Trim MCP tool descriptions longer than this. */
const DESC_LIMIT = 400
/** Tool-id prefixes whose descriptions are known to be bloated. */
const TRIM_PREFIXES = ["serena", "context7"]

export const LocalLLM: Plugin = async ({ $, directory, client }) => {
  const sh = (cmd: string) => $`sh -c ${cmd}`.cwd(directory).nothrow().quiet()

  /** True if `bin` resolves on PATH. Keeps auto-detection honest cross-platform. */
  const resolves = async (bin: string): Promise<boolean> => {
    try {
      const r = await $`sh -c ${`command -v ${bin}`}`.cwd(directory).nothrow().quiet()
      return r.exitCode === 0
    } catch {
      return false
    }
  }

  const detectVerify = async (): Promise<string | null> => {
    const env = process.env.OPENCODE_VERIFY_CMD
    if (env && env.trim()) return env.trim()

    const has = (f: string) => existsSync(join(directory, f))

    if (has(".opencode/verify.sh")) return "sh .opencode/verify.sh"

    for (const jf of ["justfile", "Justfile", ".justfile"]) {
      if (!has(jf)) continue
      try {
        if (readFileSync(join(directory, jf), "utf8").includes("verify-fast")) {
          if (await resolves("just")) return "just verify-fast"
        }
      } catch {
        /* unreadable justfile — fall through to auto-detect */
      }
    }

    // Auto-detect: only enable a check whose binary actually resolves, so this
    // stays silent in repos (like this one) that have no Python/TS toolchain.
    const parts: string[] = []
    const pyProject =
      has("pyproject.toml") || has("ruff.toml") || has(".ruff.toml")
    if (pyProject && (await resolves("ruff"))) parts.push("ruff check .")

    if (has("tsconfig.json")) {
      const localTsc = join(directory, "node_modules", ".bin", "tsc")
      if (existsSync(localTsc)) parts.push(`"${localTsc}" --noEmit`)
      else if (await resolves("tsc")) parts.push("tsc --noEmit")
    }

    return parts.length ? parts.join(" && ") : null
  }

  const VERIFY = await detectVerify()

  /** Run VERIFY with a hard timeout. null = passed or not applicable. */
  const runVerify = async (): Promise<string | null> => {
    if (!VERIFY) return null
    let timer: ReturnType<typeof setTimeout> | undefined
    try {
      const timeout = new Promise<"timeout">((res) => {
        timer = setTimeout(() => res("timeout"), TIMEOUT_MS)
      })
      const result = await Promise.race([sh(VERIFY), timeout])
      if (result === "timeout") {
        return `verify command exceeded ${TIMEOUT_MS / 1000}s and was abandoned: ${VERIFY}`
      }
      if (result.exitCode === 0) return null // SILENT ON PASS
      const raw = `${result.stdout?.toString() ?? ""}${result.stderr?.toString() ?? ""}`.trim()
      if (!raw) return `verify failed (exit ${result.exitCode}) with no output: ${VERIFY}`
      const lines = raw.split("\n")
      const clipped =
        lines.length > MAX_LINES
          ? `${lines.slice(0, MAX_LINES).join("\n")}\n… (${lines.length - MAX_LINES} more lines suppressed)`
          : raw
      return clipped.length > MAX_CHARS ? `${clipped.slice(0, MAX_CHARS)}…` : clipped
    } catch (err) {
      return `verify command errored: ${String(err)}`
    } finally {
      if (timer) clearTimeout(timer)
    }
  }

  let lastRun = 0
  const nudges = new Map<string, number>()

  return {
    /**
     * PostToolUse equivalent. Appends failures to the tool result the model reads,
     * so a bad edit is corrected on the next turn rather than N turns later.
     */
    "tool.execute.after": async (input, output) => {
      if (!VERIFY) return
      if (!EDIT_TOOLS.has(input.tool)) return
      const now = Date.now()
      if (now - lastRun < DEBOUNCE_MS) return
      lastRun = now

      const failure = await runVerify()
      if (!failure) return
      output.output +=
        `\n\n<verify status="fail" command="${VERIFY}">\n${failure}\n</verify>\n` +
        `Fix these before continuing. Do not start unrelated work while verification is failing.`
    },

    /**
     * Stop-hook equivalent. When the agent goes idle it believes it is finished;
     * re-verify and push it back to work if it is not. MAX_NUDGES bounds the loop.
     */
    event: async ({ event }) => {
      if (!VERIFY) return
      if (event.type !== "session.idle") return
      const sessionID = event.properties?.sessionID
      if (!sessionID) return

      const used = nudges.get(sessionID) ?? 0
      if (used >= MAX_NUDGES) return

      const failure = await runVerify()
      if (!failure) {
        nudges.delete(sessionID) // clean finish; reset budget for later turns
        return
      }
      nudges.set(sessionID, used + 1)

      // Fire-and-forget: awaiting would block this event handler for the whole
      // follow-up turn.
      void client.session
        .prompt({
          path: { id: sessionID },
          body: {
            parts: [
              {
                type: "text",
                text:
                  `Verification is still failing after you stopped (attempt ${used + 1}/${MAX_NUDGES}).\n\n` +
                  `<verify status="fail" command="${VERIFY}">\n${failure}\n</verify>\n\n` +
                  `Fix these specific errors, re-run the verify command yourself to confirm, ` +
                  `then stop. If you believe an error is pre-existing and unrelated to your ` +
                  `change, say so explicitly instead of silently ignoring it.`,
              },
            ],
          },
        })
        .catch(() => {
          /* session may have been closed/aborted — nothing useful to do here */
        })
    },

    /**
     * Tool-budget control. Bloated MCP descriptions crowd out real context on a
     * 35B model. Keeps the first paragraph (which carries the actual signal) and
     * drops the prose tail. Parameters are left untouched — trimming those would
     * break tool calls.
     */
    "tool.definition": async (input, output) => {
      if (!TRIM_PREFIXES.some((p) => input.toolID.startsWith(p))) return
      const desc = output.description
      if (!desc || desc.length <= DESC_LIMIT) return
      const firstPara = desc.split(/\n\s*\n/)[0]!.trim()
      output.description =
        firstPara.length <= DESC_LIMIT ? firstPara : `${firstPara.slice(0, DESC_LIMIT).trimEnd()}…`
    },
  }
}
