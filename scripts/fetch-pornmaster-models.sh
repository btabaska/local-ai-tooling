#!/usr/bin/env bash
# fetch-pornmaster-models.sh — (re)download the PornMaster image-gen model sets
# into the rig ComfyUI model tree (/opt/comfyui/models/*).
#
# Two NSFW image checkpoints, both sized for the 3090 Ti (24GB):
#   1. PornMaster-Anime IL-V5  — Illustrious/NoobAI SDXL, all-in-one (6.6GB fp16).
#        Recommended: Euler a, 30 steps, CFG 5, 832x1216 / 1024x1024.
#   2. PornMaster Krea2 V2 Turbo — Krea-2 (Qwen-Image class) fp8 UNet (12.2GB).
#        Needs the Qwen3-VL-4B text encoder (CLIPLoader type 'krea2') + Qwen-Image VAE.
#        Recommended: euler/simple, 8 steps, CFG 1.0, FluxGuidance NOT used.
#        Negatives: raise CFG to 1.5 and swap ConditioningZeroOut for a real negative.
#
# NOTE: Krea2's newest version (V2.5 Turbo) is Civitai Early-Access (needs paid Buzz).
# This script pulls the freely-downloadable V2 Turbo fp8. To use V2.5, unlock it on
# Civitai first, then swap the model-version id below (3112108 -> 3171380).
#
# Requires: curl + the Civitai API key (vault: civitai.api_key) for the checkpoints.
#   CIVITAI_TOKEN=<key> ./fetch-pornmaster-models.sh
set -euo pipefail
MODELS=${COMFY_MODELS_DIR:-/opt/comfyui/models}
: "${CIVITAI_TOKEN:?set CIVITAI_TOKEN (vault: civitai.api_key)}"
mkdir -p "$MODELS"/{checkpoints,diffusion_models,text_encoders,vae}

dl() { # url dest [civitai]
  local url="$1" dest="$2" auth="${3:-}"
  if [ -s "$dest" ]; then echo "skip (exists): $dest"; return; fi
  echo ">> $dest"
  if [ "$auth" = civitai ]; then curl -fSL -H "Authorization: Bearer $CIVITAI_TOKEN" -C - -o "$dest" "$url"
  else curl -fSL -C - -o "$dest" "$url"; fi
}

# 1. PornMaster-Anime IL-V5 (Illustrious SDXL, all-in-one) — Civitai model 1033851 / ver 2518034
dl "https://civitai.com/api/download/models/2518034" \
   "$MODELS/checkpoints/pornmasterAnime_ilV5.safetensors" civitai

# 2. PornMaster Krea2 V2 Turbo fp8 (Krea-2 / Qwen-Image UNet) — Civitai model 2735032 / ver 3112108
dl "https://civitai.com/api/download/models/3112108" \
   "$MODELS/diffusion_models/pornmasterKrea2_v2Turbo_fp8.safetensors" civitai
#    Krea2 companions (public HF, no token):
dl "https://huggingface.co/Comfy-Org/Krea-2/resolve/main/text_encoders/qwen3vl_4b_fp8_scaled.safetensors" \
   "$MODELS/text_encoders/qwen3vl_4b_fp8_scaled.safetensors"
dl "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors" \
   "$MODELS/vae/qwen_image_vae.safetensors"

echo "PornMaster model sets complete. ComfyUI auto-rescans model folders (no restart needed)."
echo "Workflows: comfyui-workflows/convert-ui.sh deploys pornmaster-{anime-il,krea2-turbo} to the sidebar."
