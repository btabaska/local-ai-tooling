# Historical build handoffs — retired (ai-07, 2026-07-29)

These are **point-in-time build handoffs**, kept for the record. They describe
what was planned/built at a moment in time — and in places the pre-migration
**Ollama-native** design — so they **no longer reflect the running stack**.

**Current truth lives in two places:**
- the repo **[`../README.md`](../README.md)** — layout, setup, rebuild, publishing;
- the wiki design page **https://wiki.tabaska.us/architecture/local-ai-build/**
  (source `foss-setup/wiki/docs/architecture/local-ai-build.md`) — shipped
  design, model lineup, measured VRAM ceilings, bake-off, daily-use guide.

| File | What it was | Superseded by |
|---|---|---|
| `INSTRUCTIONS.md` | Original Ollama-native rig + MacBook setup walkthrough (pre-ai-01). | README §Setup/rebuild + wiki. |
| `HANDOFF-ai-01.md` | ai-01 Ollama→llama.cpp/llama-swap migration build handoff. | Wiki (shipped design). |
| `HANDOFF-ai-02-frontend-wiring.md` | ai-02 Marinara/Lumiverse + ComfyUI wiring handoff. Still-useful frontend quirks. | Wiki + live apps. |
| `legacy-ollama-native-README.md` | The pre-ai-01 README's Ollama-native design narrative. | Current README + wiki. |

Do not cite these as current. Where they and the wiki disagree, the wiki wins.
