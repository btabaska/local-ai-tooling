# PornMaster image models (rig ComfyUI)

Two NSFW image-generation checkpoints added to rig ComfyUI (`:8188`) on 2026-08-06,
both sized for the 3090 Ti (24GB). Driven from the ComfyUI web UI (Workflows sidebar).
Both verified end-to-end (test renders produced valid PNGs).

## Models & recommended settings

### PornMaster-Anime IL-V5  (Illustrious / NoobAI SDXL)
- `checkpoints/pornmasterAnime_ilV5.safetensors` — fp16 6.6GB, all-in-one (bundles CLIP+VAE).
- **Recommended:** sampler **Euler a**, **30 steps**, **CFG 5**, **832×1216** (portrait) or 1024×1024.
- Quality tags help: positive `masterpiece, best quality, amazing quality, very aesthetic, absurdres`;
  negative `worst quality, low quality, bad anatomy, bad hands, ... censored`.
- Peak VRAM ~7.6GB — trivial for this card.
- Workflow: **`pornmaster-anime-il`** (sidebar).

### PornMaster Krea2 V2 Turbo  (Krea-2 / Qwen-Image class)
- `diffusion_models/pornmasterKrea2_v2Turbo_fp8.safetensors` — **fp8 12.2GB** UNet.
  (bf16 is 24.5GB → would pin the whole card; fp8 is the 24GB build.)
- **NOT a Flux.1 model.** It is Krea-2 (Qwen-Image architecture) and needs:
  - Text encoder `text_encoders/qwen3vl_4b_fp8_scaled.safetensors` (Qwen3-VL-4B),
    loaded with **`CLIPLoader` type `krea2`** (not DualCLIPLoader/t5xxl — that errors with
    "expects 12×2560=30720 features … Load the text encoder with CLIPLoader type 'krea2'").
  - VAE `vae/qwen_image_vae.safetensors` (the Qwen-Image VAE, not the Flux `ae`).
- **Recommended (Turbo):** sampler **euler**, scheduler **simple**, **8 steps**, **CFG 1.0**,
  **1024×1024**. No FluxGuidance node. Negative prompt is zeroed at CFG 1.
  - To use a **real negative prompt**: raise CFG to **1.5** and replace the `ConditioningZeroOut`
    with a second `CLIPTextEncode` (per the model author).
- Peak VRAM ~18.5GB — fits with headroom.
- Workflow: **`pornmaster-krea2-turbo`** (sidebar).
- **Version note:** the newest **V2.5 Turbo** is Civitai **Early-Access (paid Buzz)**. This is the
  freely-downloadable **V2 Turbo**. To move to V2.5: unlock it on Civitai, then change the
  Civitai version id `3112108 → 3171380` in `scripts/fetch-pornmaster-models.sh`.

## Files / rebuild
`CIVITAI_TOKEN=<vault:civitai.api_key> scripts/fetch-pornmaster-models.sh`

| file | dir | source |
|------|-----|--------|
| `pornmasterAnime_ilV5.safetensors` | `checkpoints/` | Civitai 1033851 v2518034 |
| `pornmasterKrea2_v2Turbo_fp8.safetensors` | `diffusion_models/` | Civitai 2735032 v3112108 |
| `qwen3vl_4b_fp8_scaled.safetensors` | `text_encoders/` | HF `Comfy-Org/Krea-2` |
| `qwen_image_vae.safetensors` | `vae/` | HF `Comfy-Org/Qwen-Image_ComfyUI` |

Workflows are generated from the `.api.json` sources by `comfyui-workflows/convert-ui.sh`
(uses live `/object_info`) and deployed to `/opt/comfyui/user/default/workflows/`.
ComfyUI auto-rescans model folders — no container restart needed after adding models.

## Operational note
These are image models (seconds per image), so unlike LTX video they're fine to run through
the day. They still share the 3090 Ti with the LTX video stack and Immich ML — ComfyUI
serializes its own queue, but a running LTX video job will delay an image job until it finishes.
