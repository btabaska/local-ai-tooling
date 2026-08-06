#!/usr/bin/env bash
# fetch-ltx23-video.sh — (re)download the LTX-2.3 "10Eros" video-generation model
# set into the rig ComfyUI model tree (/opt/comfyui/models/*).
#
# Rebuild path for the LTX-2.3 22B video stack driven from ComfyUI (:8188) on rig.
# ComfyUI 0.28+ has NATIVE LTX-2.3 nodes — no custom node pack required. This is a
# STANDALONE video capability (run via the ComfyUI web UI, daytime preferred — it
# contends with Immich ML on the 3090 Ti during the 01:00-07:00 EDT ML window and
# holds the GPU for minutes per clip). It is NOT wired into the OWUI image-gen
# arbiter (:8189).
#
# The "10Eros" checkpoint is an abliterated base-LTX-2.3 merge published on Civitai
# (model 2447875, v1.4). fp8 (~27GB) is the 24GB-VRAM-capable build; bf16 (~44GB)
# is higher quality but does not fit a 3090 Ti well. Companion files (Gemma text
# encoder, distilled + abliterated LoRAs, spatial upscaler) come from the public
# Comfy-Org / Lightricks Hugging Face repos.
#
# Requires: curl, plus the Civitai API key for the checkpoint + VAEs.
#   Civitai key path in the handoff vault: civitai.api_key
#   Pass it via env:  CIVITAI_TOKEN=<key> ./fetch-ltx23-video.sh
set -euo pipefail

MODELS=${COMFY_MODELS_DIR:-/opt/comfyui/models}
: "${CIVITAI_TOKEN:?set CIVITAI_TOKEN (vault: civitai.api_key)}"

mkdir -p "$MODELS"/{checkpoints,text_encoders,vae,loras,latent_upscale_models}

dl() { # url dest [auth]
  local url="$1" dest="$2" auth="${3:-}"
  if [ -s "$dest" ]; then echo "skip (exists): $dest"; return; fi
  echo ">> $dest"
  if [ "$auth" = "civitai" ]; then
    curl -fSL -H "Authorization: Bearer $CIVITAI_TOKEN" -C - -o "$dest" "$url"
  else
    curl -fSL -C - -o "$dest" "$url"
  fi
}

# --- checkpoint (Civitai 2447875 v1.4, fp8 ~27GB) ---
dl "https://civitai.com/api/download/models/3109610?type=Model&format=SafeTensor&fp=fp8" \
   "$MODELS/checkpoints/ltx2310eros_v14.safetensors" civitai

# --- video + audio VAE (Civitai 2447875 v1) — fallback; native nodes can also read VAE from the checkpoint ---
dl "https://civitai.com/api/download/models/2892069?type=VAE&format=Other&fp=bf16" \
   "$MODELS/vae/LTX23_video_vae_bf16.safetensors" civitai
dl "https://civitai.com/api/download/models/2892069?type=VAE&format=Other&fp=fp16" \
   "$MODELS/vae/LTX23_audio_vae_bf16.safetensors" civitai

# --- Gemma-3-12B text encoder (LTX-2.3 uses Gemma, not T5) ---
dl "https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors" \
   "$MODELS/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors"

# --- distilled LoRA (few-step sampling, strength ~0.5) + abliterated-Gemma LoRA (uncensors the text encoder) ---
dl "https://huggingface.co/Comfy-Org/ltx-2.3/resolve/main/split_files/loras/ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16.safetensors" \
   "$MODELS/loras/ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16.safetensors"
dl "https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/loras/gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors" \
   "$MODELS/loras/gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors"

# --- spatial upscaler (stage-2 of the official two-stage workflow) ---
dl "https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.1.safetensors" \
   "$MODELS/latent_upscale_models/ltx-2.3-spatial-upscaler-x2-1.1.safetensors"

echo "LTX-2.3 model set complete. Restart ComfyUI to register new files:"
echo "  docker restart comfyui"
echo "Then load workflow: user/default/workflows/LTX-2.3_10Eros_{T2V,I2V}.json"
