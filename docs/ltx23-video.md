# LTX-2.3 "10Eros" — local video generation (rig ComfyUI)

Local text-to-video / image-to-video on the rig via ComfyUI (`:8188`), using the
**LTX-2.3 22B** model with the Civitai **"10Eros"** abliterated merge (model 2447875).
Shipped 2026-08-06. Runs entirely on the 3090 Ti (24GB) — no cloud.

## What it is / why it fits 24GB

- **Base:** LTXV 2.3 (Lightricks), a 22B audio+video diffusion transformer.
- **Checkpoint:** `ltx2310eros_v14.safetensors` — the **fp8** build (~27GB on disk).
  fp8 is the 24GB-VRAM-capable variant; bf16 (~44GB) is higher quality but does not
  fit a 3090 Ti. Verified peak VRAM **23.5GB / 24GB** at 512×320×25 frames.
- ComfyUI **0.28+ supports LTX-2.3 natively** — no custom node pack. Fully additive;
  the OWUI image-gen pipeline (z-image / flux-2) was untouched.

## Files (all under `/opt/comfyui/models/`)

| file | dir | source |
|------|-----|--------|
| `ltx2310eros_v14.safetensors` (fp8, 27GB) | `checkpoints/` | Civitai 2447875 v1.4 |
| `gemma_3_12B_it_fp4_mixed.safetensors` (8.8GB) | `text_encoders/` | HF `Comfy-Org/ltx-2` |
| `LTX23_video_vae_bf16.safetensors` (1.4GB) | `vae/` | Civitai 2447875 v1 |
| `LTX23_audio_vae_bf16.safetensors` (348MB) | `vae/` | Civitai 2447875 v1 |
| `ltx_2.3_22b_distilled_1.1_lora_...bf16.safetensors` (2.6GB) | `loras/` | HF `Comfy-Org/ltx-2.3` |
| `gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors` (595MB) | `loras/` | HF `Comfy-Org/ltx-2` |
| `ltx-2.3-spatial-upscaler-x2-1.1.safetensors` (950MB) | `latent_upscale_models/` | HF `Lightricks/LTX-2.3` |

Rebuild the whole set: `CIVITAI_TOKEN=<vault:civitai.api_key> scripts/fetch-ltx23-video.sh`

**LTX-2.3 uses Gemma-3-12B as its text encoder** (not T5). The `LTXAVTextEncoderLoader`
node loads the Gemma file + the checkpoint (for the text-projection layer); the
checkpoint's own CLIP slot is intentionally empty (a harmless "no CLIP/text encoder
weights in checkpoint" warning is expected). The video VAE is read from the checkpoint;
the separate `LTX23_video_vae` file is a fallback.

## How to run

Open ComfyUI at `http://rig:8188` → Workflows → these are pre-installed with the
10Eros model already selected:

- **`LTX-2.3_10Eros_T2V.json`** — text-to-video
- **`LTX-2.3_10Eros_I2V.json`** — image-to-video (attach a start frame)

Both are the official ComfyUI two-stage templates (base gen → spatial upscale → refine,
+ optional audio + an LLM prompt-enhancer node). Repo mirror: `comfyui-workflows/ltx-video/`.
`ltx23-verify.api.json` is a stripped single-stage API graph used for the deploy smoke test.

### Prompting
LTX-2.3 wants **cinematic scene-script prompts** — describe action over time, visual
detail, and (optionally) audio/dialogue. Terse tag-style prompts transfer poorly. The
10Eros author recommends refining prompts with an uncensored LLM into a shot description.

## Operational rules (IMPORTANT — GPU contention)

- **Daytime only, by default.** Video gen holds the whole 3090 Ti for minutes per clip.
  The rig Immich-ML window pins ~13GB of VRAM **01:00–07:00 EDT** (`immich-ml-window`);
  running LTX then risks OOM / evicting ML. By day the card is free.
- **Not wired into the OWUI arbiter (`:8189`)** on purpose — a minutes-long video job
  would block the household z-image/flux image pipeline. This is a **standalone** tool
  driven from the ComfyUI web UI. (Ask before wiring it into OWUI.)
- Force the card free at night if needed: `systemctl start immich-ml-window@off.service`
- 1080p / longer clips work but offload more to system RAM (62GB) and run slower;
  4K ~10s clips are ~20-25 min.

## Content note
"10Eros" is an NSFW-capable merge; the abliterated-Gemma LoRA uncensors the text encoder.
Single-user, local, off-tailnet-exposed only via the existing rig ComfyUI port.
