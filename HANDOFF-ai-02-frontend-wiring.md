# HANDOFF ai-02 — Marinara + Lumiverse fully wired to the creative stack (2026-07-18)

Session goal (full original brief in the appendix): wire all creative/RP models —
cydonia / dolphin-venice / goetia (LLM) and Z-Image Turbo / NoobAI-XL / Flux.2 Klein
(image) — into BOTH frontends end to end, with take-turns GPU arbitration proven and
everything codified.

**Status: done.** All 6 models work through both apps via the public HTTPS paths, with
per-model completion + real-image evidence and the arbiter unload/free cycle observed in
logs on every generation.

## What changed

### 1. gpu-arbiter unload hook was dead — fixed (docker/gpu-arbiter.py)
The proxy matched `request.path == "/prompt"` exactly, but the ComfyUI web UI and modern
API clients POST `/api/prompt` — 58 such POSTs since the 06:27Z restart had produced
**zero** LLM unloads (the take-turns behavior only worked by llama-swap TTL luck; a gen
submitted while a 22.8 GiB LLM was resident would have OOMed). Now matches
`("/prompt", "/api/prompt")`, and the WS proxy matches `("/ws", "/api/ws")`.
NOTE: the container must be **recreated** (not restarted) after editing the file — it is
a single-file bind mount and `sed -i` swaps the inode.

### 2. Scoped keys injected via compose (docker-compose.yml)
`MARINARA_LITELLM_KEY` and `LUMIVERSE_LITELLM_KEY` are now in each container's
environment. Neither app reads env for connections (verified in both sources) — the vars
exist so the seed scripts can rebuild connections after a volume wipe.

### 3. Marinara connections (via its REST API, localhost:3002)
| name | change |
|---|---|
| **LiteLLM Creative** (was "Goetia", `jnChmREY40M4wJ1YCkg60`) | base_url `http://litellm:4000/v1` → `https://llm.tabaska.us/v1`, key re-set from env, model goetia, maxContext 73728, now `isDefault` + `defaultForAgents` |
| "New Connection" empty stub | deleted |
| **Anime Image** (`tx7fR4WpXY7E3Hyq_Ua63`) | untouched (was already correct) |
| **Realistic Image (Z-Image Turbo)** (`WKaZtAjhPPUBtJcnPlgI7`) | new; workflow = `comfyui-workflows/marinara/z-image-turbo-realistic.marinara.json` verbatim |
| **Realistic Image (Flux.2 Klein)** (`yAkI78skOar8mAUDj1zsB`) | new; workflow = `marinara/flux2-klein-9b.marinara.json`; **model field = `klein-9b-comfyui`** (see quirks) |
| OpenRouter Free | left in place, no longer default (cannot be deleted — reseeded at startup) |

### 4. Lumiverse connections (via its authenticated REST API, rig:3001)
| name | change |
|---|---|
| **LiteLLM Creative** (was "Goetia", `c385c001-…`) | api_url → `https://llm.tabaska.us/v1`, key re-set to `LUMIVERSE_LITELLM_KEY`, is_default |
| **Anime Image (NoobAI-XL)** (`b6074855-…`, default) | new; imported `noobai-xl-anime.api.json` (unwrapped), 10 field mappings incl. steps/cfg/sampler/scheduler/denoise |
| **Realistic Image (Z-Image Turbo)** (`2f3a12ad-…`) | new; 4 mappings (prompt/seed/w/h; no negative node, turbo steps/cfg pinned) |
| **Realistic Image (Flux.2 Klein)** (`a9b09046-…`) | new; 7 mappings (w/h mapped on BOTH latent node 6 and Flux2Scheduler node 8) |

### 5. Seed scripts (the codify answer for "connections live only in data volumes")
- `scripts/seed-marinara-connections.sh`
- `scripts/seed-lumiverse-connections.sh`

Idempotent (upsert by name), read keys from `docker/.env`, workflows from the repo files,
and self-test each connection. After a volume wipe: run both, done. Connections remain
**UI-visible state in encrypted app DBs** — the scripts are the reproducibility layer;
env/compose alone cannot express them (neither app supports it).

## Acceptance evidence (2026-07-18 03:15–03:50 EDT)

- **Keys/scoping**: both keys return exactly `[cydonia, dolphin-venice, goetia]` from
  `https://llm.tabaska.us/v1/models` (and localhost).
- **LLM completions** (public URL): all 3 models × both keys returned non-empty content
  (e.g. cydonia: "I'm part of the Mistral model family…"). Two first-load attempts
  returned llama-swap 500s because the *user's own live image jobs* preempted the loads
  mid-flight — that is the take-turns design working; retries succeeded.
- **In-app LLM**: Marinara `POST /:id/test-message` succeeded for all 3 models (connection
  model swapped per test, left on goetia). Lumiverse `POST /api/v1/generate/quiet`
  returned a real completion through its default connection.
- **Images, in-app (Lumiverse)**: 3/3 `POST /api/v1/image-gen/generate` succeeded —
  `noobai_test_00003_.png` (18s), `zimage_test_00002_.png` (21s), `flux2_test_00002_.png`
  (62s), each with `generated:true` + imageUrl.
- **Images, Marinara path**: replicated `generateComfyUI()` byte-exactly (same
  substitution incl. quote-preserved numerics, same `POST {base}/prompt`) against the
  workflows read back from Marinara's DB → `marinara_zimage_00002_.png` (1.3 MB PNG),
  `marinara_flux_00002_.png` (1.6 MB PNG), `node_errors: {}`.
- **Take-turns, every single gen**: pre-check showed `goetia-24b` resident → arbiter
  logged `LLM unloaded before generation` → gen success → `ComfyUI freed (queue
  drained)` → next chat reloaded the LLM. Also continuously validated by the user's own
  `/api/prompt` traffic after the fix.

## Quirks / lessons (do not re-learn these)

1. **Marinara flux keyword misroute**: `inferImageSource()` maps any model containing
   `flux`/`black-forest` to TogetherAI *before* the comfyui base-URL rule. The Flux
   connection's model field must avoid the substring (`klein-9b-comfyui`). `POST /:id/test`
   does NOT catch it (tests dispatch on base URL only). Verified with the app's own code.
2. **Quoted numeric placeholders are fine**: Marinara replaces tokens inside JSON string
   quotes ("%seed%" → "12345" as a *string*); ComfyUI coerces. Don't unquote templates.
3. **Both apps call providers server-side** (Fastify / Bun backends). Internal docker
   URLs would also work — the public URLs were chosen per the brief (uniform, browser-safe,
   CORS verified `*` on LiteLLM and ComfyUI; Caddy adds no CORS). Cost: chat/image in both
   apps now depends on mini Caddy + DNS. Fallback if mini is down: point base URLs back to
   `http://litellm:4000/v1` / `http://gpu-arbiter:8189` (compose network).
4. **Marinara 1.5.0 API is unauthenticated** on rig:3002 (only `/api/admin/*` checks
   `X-Admin-Secret`); the mini Caddy basic_auth is the only real gate (documented in
   compose). The seed script leans on this via localhost.
5. **Lumiverse**: every direct request needs `Host: lumiverse.tabaska.us`; sign-in
   rate-limit 8/5min + lockout; `/api/v1/*` needs a BetterAuth bearer token
   (`set-auth-token` response header). Image connection choice at generation time is the
   user's `imageGeneration.activeImageGenConnectionId` **setting**, not `is_default`.
6. **OpenRouter Free** ships a hardcoded public OpenRouter key baked into the marinara
   image and reseeds itself at every startup if the row id is missing.
7. **Lumiverse image import** wants the bare node map (unwrap `.prompt` from the
   `*.api.json` files) and fetches the target `/object_info` live at import time.

8. **Agent wiring in Marinara** (found 2026-07-18, illustrator 405): an agent row has
   TWO connection fields — `connectionId` = its TEXT LLM, `settings.imageConnectionId` =
   its image connection. Setting the image connection into `connectionId` makes the
   agent POST chat/completions at ComfyUI → "OpenAI API error 405: Method Not Allowed".
   Illustrator agent fixed to connectionId=LiteLLM Creative + imageConnectionId=Flux;
   agents also only run when the CHAT opts in (metadata.enableAgents=true +
   activeAgentIds contains the agent type; PATCH /api/chats/:id/metadata).
9. **Vision ENABLED on the creative trio (2026-07-18, same day)**: image attachments
   used to fail with LiteLLM 500 "provide the mmproj". Fixed: downloaded the shared
   Mistral-Small-3.2-2506 vision tower (unsloth mmproj-F16.gguf, 838 MB) to
   /opt/llm/models/mmproj-mistral-small-3.2-f16.gguf, added --mmproj to all three
   models in llama-swap-config.yaml, and cut ctx 73728 -> 61440 (65536 measured only
   0.5 GiB free with desktop overhead; 61440 restores the ~1 GiB headroom norm).
   Verified: all three models describe a test image correctly through the public
   path + MARINARA key; peak VRAM 23.85/24.56 GiB. The mmproj file is a model
   artifact (not in git) — re-download from
   huggingface.co/unsloth/Mistral-Small-3.2-24B-Instruct-2506-GGUF if lost.

10. **Marinara placeholder whitelist** (found 2026-07-18, illustrator + NoobAI): the
   in-app substitution (`generateComfyUI`) replaces ONLY `%prompt%`,
   `%negative_prompt%`, `%width%`, `%height%`, `%seed%`, `%model%`,
   `%reference_image%`. Any other token (`%sampler%`, `%steps%`, `%cfg%`,
   `%scheduler%`, `%denoise%`) passes through raw and fails ComfyUI validation
   (`value_not_in_list`). The NoobAI marinara template carried those extra tokens —
   an in-app generation with it had NEVER actually worked (its connection `/test`
   only probes `/system_stats`). Fixed by hard-coding steps=28 cfg=5.0
   euler_ancestral/normal denoise=1.0 in
   `comfyui-workflows/marinara/noobai-xl-anime.marinara.json` + reseed; verified
   end-to-end via the illustrator (marinara_noobai render success). Keep new
   Marinara templates to the whitelist.

11. **Illustrator agent config (2026-07-18)**: image connection = Anime Image
   (NoobAI-XL); promptTemplate = danbooru tag-style prompting (source of truth:
   docs/marinara-illustrator-tag-prompt.txt — agent rows live only in the
   marinara-data volume, so after a wipe re-paste it via the agent settings UI or
   PATCH /api/agents/:id {"promptTemplate": <file contents>}). Verified end to end:
   goetia emits tag prompts, marinara_noobai renders succeed.

12. **CharacterTavern card downloads (2026-07-18)**: "Failed to download character
   card" — CharacterTavern moved card storage from cards.character-tavern.com
   (now 403s all clients) to ct-cards.storage.character-tavern.com; Marinara
   1.5.0 ships the old host and no newer image exists (GHCR semver tops out at
   1.5.0; git tags v2.3.x have no image). Fix = patched routes file bind-mounted
   over the image copy (docker/patches/bot-browser-chartavern.routes.js, mount
   in compose) — verified via GET /api/bot-browser/chartavern/download/... ->
   200 PNG. REMOVE the mount when bumping the image.

## Image-input ComfyUI workflows (added 2026-07-18, for comfyui.tabaska.us)

Three image-input flows, authored + render-verified via the arbiter, live in the
ComfyUI web UI's Workflows sidebar (deployed to /opt/comfyui/user/default/workflows/):

| sidebar name | does | main knobs |
|---|---|---|
| img2img-noobai-variations | anime restyle/variations of an input image | KSampler denoise (0.3 subtle / 0.6 restyle / 0.75+ reimagine), prompt, seed |
| img2img-zimage-variations | photoreal variations (Z-Image turbo, 8 steps) | denoise (same scale), prose prompt; keep steps 8 / cfg 1 (distill recipe) |
| edit-flux2-klein | TRUE instruction editing ("make it winter") via ReferenceLatent | edit instruction prompt; cfg 3-5 = edit strength vs source fidelity; no denoise knob |

Sources of truth in this repo: comfyui-workflows/*.api.json (executable, verified) and
comfyui-workflows/ui/*.json (UI-format, generated by scripts/comfyui-api-to-ui.py — a
generic API->UI converter that derives widget order/slots from live /object_info; rerun
it + copy to the workflows dir after editing an api.json). Input images: drop files in
/opt/comfyui/input/ on rig (or use LoadImage's upload button); LoadImage lists that dir.
Gotcha found while authoring: ComfyUI 0.28 treats ImageScaleToTotalPixels.resolution_steps
as required despite its default — API-format graphs must set it explicitly.

## Known gaps (deliberate)

- **Civitai token**: only base HF checkpoints are installed; premium/NSFW retrains need a
  Civitai API token that is not in the vault. Nothing fetched. Decision + token needed
  from Brandon.
- **ComfyUI public exposure**: `comfyui.tabaska.us` (arbiter) has no auth at any layer;
  `/queue`+`/history` expose full prompts of running jobs to anyone with the URL. Was
  already true; flagging for a hardening decision (Caddy basic_auth would break the
  frontends' server-side calls unless creds are added to their base URLs).
- **Monitoring**: new consumer-end checks added to `foss-setup/verification/checks.d/rig.yaml`
  (Home repo) — connection rows present in both apps, arbiter hook regression guard,
  public-path scoped-key checks. Remaining blind spot documented there: recurring checks
  do NOT run real generations (established pattern — too heavy for the loop), so a broken
  workflow JSON inside a connection row would only surface at use time.
- The live z-image UI experiments used CLIPLoader type `stable_diffusion`; the repo
  workflows use `lumina2` (both render; `lumina2` is the architecture-correct loader and
  is what's codified).

## Appendix: original task brief (verbatim)

> Wire ALL creative/RP models into BOTH Marinara and Lumiverse — end to end. Get every
> creative/RP model in this homelab fully wired into BOTH frontend apps — Marinara and
> Lumiverse — working end to end, with all tooling and custom configs functional, and
> (wherever possible) reproducible in compose/env or each app's config API rather than
> only clicked-in via the UI.
>
> Creative LLMs (primary three): cydonia (Cydonia 24B v4.3), dolphin-venice
> (Dolphin-Mistral 24B Venice), goetia (Goetia 24B v1.3). Scoped keys expose ONLY these
> three. Image models (all three): Z-Image Turbo (realistic), NoobAI-XL v1.1
> (anime/Illustrious SDXL), Flux.2 Klein 9B (realistic alt).
>
> Single-GPU take-turns constraint: a creative LLM at 73k ctx uses ~22.8 GiB; an image
> model ~21 GB. They cannot co-reside. The gpu-arbiter alternates them: before any image
> job it unloads the LLM; after the queue drains it frees the image model so the LLM
> reloads. Any real test MUST observe this alternation, not just a 200.
>
> Acceptance: (a) LLM connection via https://llm.tabaska.us/v1 + the app's scoped key;
> model list = the trio; a real chat completion returns non-empty content for each of the
> three. (b) an image_generation connection via https://comfyui.tabaska.us generates a
> real image for each of the 3 workflows; take-turns verified in logs. (c) inject the
> scoped keys via env/compose; seed connections declaratively where possible.
> Verify end-to-end, not liveness. Land every change in BOTH the live host AND
> local-ai-tooling. Note the Civitai-token gap and the monitoring blind spot in the
> handoff.
