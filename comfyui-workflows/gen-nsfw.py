#!/usr/bin/env python3
"""Generate NSFW Z-Image workflows (Civitai retrains + uncensored Engineer-V4 TE).
Turbo retrains use the 8-step/cfg1 config; the Moody Wild BASE retrain uses 40/cfg4
with a real negative. Uncensored TE (Qwen3-4b-Z-Image-Engineer) via CLIPLoaderGGUF."""
import json, os
base = os.path.expanduser("~/Documents/GitHub/local-ai-tooling/comfyui-workflows")
TE = "Qwen3-4b-Z-Image-Engineer-V4-Q8_0.gguf"
NEG = "worst quality, low quality, blurry, deformed, bad anatomy, bad hands, extra limbs, watermark, text, signature"
def W(d): return {"prompt": d}
def dump(sub, fn, d):
    p = os.path.join(base, sub, fn) if sub else os.path.join(base, fn)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(d, open(p, "w"), indent=1); print(sub or "raw", fn)

def turbo(unet, prompt, w, h, seed, prefix):
    return {
        "1": {"class_type":"CLIPLoaderGGUF","inputs":{"clip_name":TE,"type":"lumina2"}},
        "2": {"class_type":"UNETLoader","inputs":{"unet_name":unet,"weight_dtype":"default"}},
        "3": {"class_type":"VAELoader","inputs":{"vae_name":"ae.safetensors"}},
        "4": {"class_type":"ModelSamplingAuraFlow","inputs":{"model":["2",0],"shift":3}},
        "5": {"class_type":"CLIPTextEncode","inputs":{"clip":["1",0],"text":prompt}},
        "6": {"class_type":"ConditioningZeroOut","inputs":{"conditioning":["5",0]}},
        "7": {"class_type":"EmptySD3LatentImage","inputs":{"width":w,"height":h,"batch_size":1}},
        "8": {"class_type":"KSampler","inputs":{"seed":seed,"steps":8,"cfg":1.0,"sampler_name":"dpmpp_sde","scheduler":"beta","denoise":1.0,"model":["4",0],"positive":["5",0],"negative":["6",0],"latent_image":["7",0]}},
        "9": {"class_type":"VAEDecode","inputs":{"samples":["8",0],"vae":["3",0]}},
        "10":{"class_type":"SaveImage","inputs":{"filename_prefix":prefix,"images":["9",0]}},
    }
def base_zi(unet, prompt, neg, w, h, seed, prefix):
    return {
        "1": {"class_type":"CLIPLoaderGGUF","inputs":{"clip_name":TE,"type":"lumina2"}},
        "2": {"class_type":"UNETLoader","inputs":{"unet_name":unet,"weight_dtype":"default"}},
        "3": {"class_type":"VAELoader","inputs":{"vae_name":"ae.safetensors"}},
        "4": {"class_type":"ModelSamplingAuraFlow","inputs":{"model":["2",0],"shift":3}},
        "5": {"class_type":"CLIPTextEncode","inputs":{"clip":["1",0],"text":prompt}},
        "6": {"class_type":"CLIPTextEncode","inputs":{"clip":["1",0],"text":neg}},
        "7": {"class_type":"EmptySD3LatentImage","inputs":{"width":w,"height":h,"batch_size":1}},
        "8": {"class_type":"KSampler","inputs":{"seed":seed,"steps":40,"cfg":4.0,"sampler_name":"euler","scheduler":"beta","denoise":1.0,"model":["4",0],"positive":["5",0],"negative":["6",0],"latent_image":["7",0]}},
        "9": {"class_type":"VAEDecode","inputs":{"samples":["8",0],"vae":["3",0]}},
        "10":{"class_type":"SaveImage","inputs":{"filename_prefix":prefix,"images":["9",0]}},
    }
P = "photorealistic portrait of a woman, natural window light, freckles, soft skin detail, sharp focus, cinematic"
# CyberRealistic Catalyst (explicit turbo) — primary NSFW realistic
dump("", "z-image-nsfw-cyberrealistic.api.json", W(turbo("cyberrealistic-nsfw-zimage-turbo.safetensors", P, 1328,1328, 7, "znsfw_cyber")))
dump("marinara", "z-image-nsfw-cyberrealistic.marinara.json", W(turbo("cyberrealistic-nsfw-zimage-turbo.safetensors", "%prompt%", "%width%","%height%", "%seed%", "marinara_znsfw_cyber")))
# Moody Real (softcore turbo)
dump("", "z-image-nsfw-moody-real.api.json", W(turbo("moody-real-zimage-turbo.safetensors", P, 1328,1328, 7, "znsfw_moodyreal")))
dump("marinara", "z-image-nsfw-moody-real.marinara.json", W(turbo("moody-real-zimage-turbo.safetensors", "%prompt%", "%width%","%height%", "%seed%", "marinara_znsfw_moodyreal")))
# Moody Wild (explicit BASE, 40/cfg4) — raw + hq
dump("hq", "z-image-nsfw-moody-wild-base.api.json", W(base_zi("moody-wild-nsfw-zimage-base.safetensors", P, NEG, 1024,1024, 7, "znsfw_moodywild")))
print("OK")
