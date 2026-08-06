#!/bin/bash
# Convert all my API workflows -> UI/graph format for the ComfyUI GUI sidebar,
# then deploy to /opt/comfyui/user/default/workflows/ (= container /basedir/...).
set -e
cd ~/Documents/GitHub/local-ai-tooling/comfyui-workflows
mkdir -p ui
C="python3 ../scripts/comfyui-api-to-ui.py"
conv(){ $C "$1" "ui/$2" "$3" && echo "  ui/$2"; }

# tuned SFW defaults
conv z-image-turbo-realistic.api.json z-image-turbo-realistic.json   "Z-Image Turbo — realistic (tuned)"
conv noobai-xl-anime.api.json         noobai-xl-anime.json           "NoobAI-XL — anime (tuned)"
conv flux2-klein-9b.api.json          flux2-klein-9b.json            "Flux.2 Klein — realistic, fast (distilled 6-step)"
# HQ (hires + FaceDetailer / base flux)
conv hq/z-image-hq.api.json           z-image-hq.json                "Z-Image HQ — hires + FaceDetailer"
conv hq/noobai-hq.api.json            noobai-hq.json                 "NoobAI HQ — hires + FaceDetailer"
conv hq/flux2-klein-base-hq.api.json  flux2-klein-base-hq.json       "Flux.2 Klein BASE HQ — 24-step max fidelity"
# NSFW
conv z-image-nsfw-cyberrealistic.api.json          z-image-nsfw-cyberrealistic.json  "Z-Image NSFW — CyberRealistic (uncensored TE)"
conv hq/z-image-nsfw-moody-wild-base.api.json      z-image-nsfw-moody-wild-base.json "Z-Image NSFW — Moody Wild (BASE 40-step)"
conv pornmaster-anime-il.api.json                  pornmaster-anime-il.json          "PornMaster-Anime IL-V5 — Illustrious (Euler a/30/cfg5)"
conv pornmaster-krea2-turbo.api.json               pornmaster-krea2-turbo.json       "PornMaster Krea2 V2 Turbo — Flux-Krea (8-step/cfg1; cfg1.5 enables neg)"

echo "=== deploy to GUI sidebar ==="
cp -f ui/z-image-turbo-realistic.json ui/noobai-xl-anime.json ui/flux2-klein-9b.json \
      ui/z-image-hq.json ui/noobai-hq.json ui/flux2-klein-base-hq.json \
      ui/z-image-nsfw-cyberrealistic.json ui/z-image-nsfw-moody-wild-base.json \
      ui/pornmaster-anime-il.json ui/pornmaster-krea2-turbo.json \
      /opt/comfyui/user/default/workflows/
echo "sidebar now has:"; ls /opt/comfyui/user/default/workflows/
echo "=== validate one converted UI file is well-formed ==="
python3 -c "import json;d=json.load(open('ui/z-image-nsfw-cyberrealistic.json'));print('nodes',len(d['nodes']),'links',len(d['links']),'version',d.get('version'))"
