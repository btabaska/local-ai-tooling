#!/usr/bin/env python3
"""Full quality-pass workflow generator (2026-07-19). Emits:
  DEFAULTS (fast, for the RP frontends): raw .api.json + Marinara .marinara.json
  HQ variants (raw, for hero shots): hires-fix (4x-UltraSharp 2nd pass) + FaceDetailer
Flux default = DISTILLED 6-step (fixed, ~10s); Flux HQ = BASE 9B 24-step (max fidelity)."""
import json, os
base = os.path.expanduser("~/Documents/GitHub/local-ai-tooling/comfyui-workflows")
def W(d): return {"prompt": d}
def dump(sub, fn, d):
    p = os.path.join(base, sub, fn) if sub else os.path.join(base, fn)
    json.dump(d, open(p, "w"), indent=1); print(("hq " if sub=="hq" else ("mar" if sub=="marinara" else "def")), fn)

NOOB_NEG = "worst quality, low quality, lowres, jpeg artifacts, bad anatomy, bad hands, extra digits, missing fingers, watermark, signature, text"

def facedetailer(nid, img, model, clip, vae, pos, neg, det, seed, steps, cfg, samp, sched, prefix):
    # FaceDetailer + its yolo detector + SaveImage. img/model/... are [node,out] refs.
    return {
        det: {"class_type":"UltralyticsDetectorProvider","inputs":{"model_name":"bbox/face_yolov8m.pt"}},
        nid: {"class_type":"FaceDetailer","inputs":{
            "image":img,"model":model,"clip":clip,"vae":vae,"positive":pos,"negative":neg,
            "bbox_detector":[det,0],"guide_size":512.0,"guide_size_for":True,"max_size":1024.0,
            "seed":seed,"steps":steps,"cfg":cfg,"sampler_name":samp,"scheduler":sched,"denoise":0.4,
            "feather":5,"noise_mask":True,"force_inpaint":True,"bbox_threshold":0.5,"bbox_dilation":10,
            "bbox_crop_factor":3.0,"sam_detection_hint":"center-1","sam_dilation":0,"sam_threshold":0.93,
            "sam_bbox_expansion":0,"sam_mask_hint_threshold":0.7,"sam_mask_hint_use_negative":"False",
            "drop_size":10,"wildcard":"","cycle":1}},
        str(int(nid)+1): {"class_type":"SaveImage","inputs":{"filename_prefix":prefix,"images":[nid,0]}},
    }

# ---------------- Z-Image ----------------
def zimage(prompt, w, h, seed, steps, cfg, samp, sched, denoise, prefix, latent=None):
    d = {
        "1":{"class_type":"CLIPLoader","inputs":{"clip_name":"qwen_3_4b.safetensors","type":"lumina2","device":"default"}},
        "2":{"class_type":"UNETLoader","inputs":{"unet_name":"z_image_turbo_bf16.safetensors","weight_dtype":"default"}},
        "3":{"class_type":"VAELoader","inputs":{"vae_name":"ae.safetensors"}},
        "4":{"class_type":"ModelSamplingAuraFlow","inputs":{"model":["2",0],"shift":3}},
        "5":{"class_type":"CLIPTextEncode","inputs":{"clip":["1",0],"text":prompt}},
        "6":{"class_type":"ConditioningZeroOut","inputs":{"conditioning":["5",0]}},
    }
    lat = latent or "7"
    if not latent:
        d["7"]={"class_type":"EmptySD3LatentImage","inputs":{"width":w,"height":h,"batch_size":1}}
    d["8"]={"class_type":"KSampler","inputs":{"seed":seed,"steps":steps,"cfg":cfg,"sampler_name":samp,"scheduler":sched,"denoise":denoise,"model":["4",0],"positive":["5",0],"negative":["6",0],"latent_image":[lat,0]}}
    d["9"]={"class_type":"VAEDecode","inputs":{"samples":["8",0],"vae":["3",0]}}
    return d
# default (fast, single pass, native 1328)
zd = zimage("photorealistic portrait of a woman with freckles and auburn hair, harbor boats and pastel houses, breezy seaside light, warm tones, cinematic close-up, sharp focus", 1328,1328, 7,8,1.0,"dpmpp_sde","beta",1.0,"zimage_test")
zd["10"]={"class_type":"SaveImage","inputs":{"filename_prefix":"zimage_test","images":["9",0]}}; dump("", "z-image-turbo-realistic.api.json", W(zd))
zm = zimage("%prompt%","%width%","%height%","%seed%",8,1.0,"dpmpp_sde","beta",1.0,"marinara_zimage")
zm["10"]={"class_type":"SaveImage","inputs":{"filename_prefix":"marinara_zimage","images":["9",0]}}; dump("marinara","z-image-turbo-realistic.marinara.json", W(zm))
# HQ: base 1024 -> hires 1.5x -> facedetailer
zh = zimage("photorealistic portrait of a woman with freckles and auburn hair, seaside, warm cinematic light, sharp focus", 1024,1024, 7,8,1.0,"dpmpp_sde","beta",1.0,"zimage_hq")
zh["10"]={"class_type":"UpscaleModelLoader","inputs":{"model_name":"4x-UltraSharp.safetensors"}}
zh["11"]={"class_type":"ImageUpscaleWithModel","inputs":{"upscale_model":["10",0],"image":["9",0]}}
zh["12"]={"class_type":"ImageScaleBy","inputs":{"image":["11",0],"upscale_method":"lanczos","scale_by":0.375}}
zh["13"]={"class_type":"VAEEncode","inputs":{"pixels":["12",0],"vae":["3",0]}}
zh["14"]={"class_type":"KSampler","inputs":{"seed":7,"steps":8,"cfg":1.0,"sampler_name":"dpmpp_sde","scheduler":"beta","denoise":0.35,"model":["4",0],"positive":["5",0],"negative":["6",0],"latent_image":["13",0]}}
zh["15"]={"class_type":"VAEDecode","inputs":{"samples":["14",0],"vae":["3",0]}}
zh.update(facedetailer("17",["15",0],["4",0],["1",0],["3",0],["5",0],["6",0],"16",7,8,1.0,"dpmpp_sde","beta","zimage_hq"))
dump("hq","z-image-hq.api.json", W(zh))

# ---------------- NoobAI ----------------
def noobai(prompt, neg, w, h, seed, denoise, prefix, latent=None):
    d = {
        "4":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":"NoobAI-XL-v1.1.safetensors"}},
        "6":{"class_type":"CLIPTextEncode","inputs":{"clip":["4",1],"text":prompt}},
        "7":{"class_type":"CLIPTextEncode","inputs":{"clip":["4",1],"text":neg}},
    }
    lat = latent or "5"
    if not latent:
        d["5"]={"class_type":"EmptyLatentImage","inputs":{"width":w,"height":h,"batch_size":1}}
    d["3"]={"class_type":"KSampler","inputs":{"seed":seed,"steps":30,"cfg":5.5,"sampler_name":"euler_ancestral","scheduler":"normal","denoise":denoise,"model":["4",0],"positive":["6",0],"negative":["7",0],"latent_image":[lat,0]}}
    d["8"]={"class_type":"VAEDecode","inputs":{"samples":["3",0],"vae":["4",2]}}
    return d
nd = noobai("masterpiece, best quality, newest, absurdres, highres, 1girl, solo, silver hair, blue eyes, ornate fantasy armor, castle courtyard, cinematic lighting, dramatic shadows", NOOB_NEG, 832,1216, 42,1.0,"noobai_test")
nd["9"]={"class_type":"SaveImage","inputs":{"filename_prefix":"noobai_test","images":["8",0]}}; dump("","noobai-xl-anime.api.json", W(nd))
nm = noobai("%prompt%","%negative_prompt%","%width%","%height%","%seed%",1.0,"marinara_noobai")
nm["9"]={"class_type":"SaveImage","inputs":{"filename_prefix":"marinara_noobai","images":["8",0]}}; dump("marinara","noobai-xl-anime.marinara.json", W(nm))
# HQ: 832x1216 -> hires 1.5x -> facedetailer
nh = noobai("masterpiece, best quality, newest, absurdres, highres, 1girl, solo, silver hair, blue eyes, ornate fantasy armor, castle courtyard, cinematic lighting", NOOB_NEG, 832,1216, 42,1.0,"noobai_hq")
nh["10"]={"class_type":"UpscaleModelLoader","inputs":{"model_name":"4x-UltraSharp.safetensors"}}
nh["11"]={"class_type":"ImageUpscaleWithModel","inputs":{"upscale_model":["10",0],"image":["8",0]}}
nh["12"]={"class_type":"ImageScaleBy","inputs":{"image":["11",0],"upscale_method":"lanczos","scale_by":0.375}}
nh["13"]={"class_type":"VAEEncode","inputs":{"pixels":["12",0],"vae":["4",2]}}
nh["14"]={"class_type":"KSampler","inputs":{"seed":42,"steps":20,"cfg":5.5,"sampler_name":"euler_ancestral","scheduler":"normal","denoise":0.35,"model":["4",0],"positive":["6",0],"negative":["7",0],"latent_image":["13",0]}}
nh["15"]={"class_type":"VAEDecode","inputs":{"samples":["14",0],"vae":["4",2]}}
nh.update(facedetailer("17",["15",0],["4",0],["4",1],["4",2],["6",0],["7",0],"16",42,20,5.5,"euler_ancestral","normal","noobai_hq"))
dump("hq","noobai-hq.api.json", W(nh))

# ---------------- Flux.2 Klein ----------------
def flux(unet, prompt, neg, w, h, seed, steps, cfg, prefix):
    return {
        "1":{"class_type":"UnetLoaderGGUF","inputs":{"unet_name":unet}},
        "2":{"class_type":"CLIPLoader","inputs":{"clip_name":"qwen_3_8b_fp8mixed.safetensors","type":"flux2","device":"default"}},
        "3":{"class_type":"VAELoader","inputs":{"vae_name":"flux2-vae.safetensors"}},
        "4":{"class_type":"CLIPTextEncode","inputs":{"clip":["2",0],"text":prompt}},
        "5":{"class_type":"CLIPTextEncode","inputs":{"clip":["2",0],"text":neg}},
        "6":{"class_type":"EmptyFlux2LatentImage","inputs":{"width":w,"height":h,"batch_size":1}},
        "7":{"class_type":"KSamplerSelect","inputs":{"sampler_name":"euler"}},
        "8":{"class_type":"Flux2Scheduler","inputs":{"steps":steps,"width":w,"height":h}},
        "9":{"class_type":"CFGGuider","inputs":{"model":["1",0],"positive":["4",0],"negative":["5",0],"cfg":cfg}},
        "10":{"class_type":"RandomNoise","inputs":{"noise_seed":seed}},
        "11":{"class_type":"SamplerCustomAdvanced","inputs":{"noise":["10",0],"guider":["9",0],"sampler":["7",0],"sigmas":["8",0],"latent_image":["6",0]}},
        "12":{"class_type":"VAEDecode","inputs":{"samples":["11",0],"vae":["3",0]}},
        "13":{"class_type":"SaveImage","inputs":{"filename_prefix":prefix,"images":["12",0]}},
    }
# default = DISTILLED, 6 steps cfg1 (fast + correct)
dump("","flux2-klein-9b.api.json", W(flux("flux-2-klein-9b-Q8_0.gguf","a vintage motorcycle in front of a retro diner at sunset, warm neon glow, cinematic photo, film grain","",1280,1280,12345,6,1.0,"flux2_test")))
dump("marinara","flux2-klein-9b.marinara.json", W(flux("flux-2-klein-9b-Q8_0.gguf","%prompt%","%negative_prompt%","%width%","%height%","%seed%",6,1.0,"marinara_flux")))
# HQ = BASE 9B, 24 steps cfg4, 1536
dump("hq","flux2-klein-base-hq.api.json", W(flux("flux-2-klein-base-9b-Q8_0.gguf","a vintage motorcycle in front of a retro diner at sunset, warm neon glow, cinematic photo, film grain, highly detailed","",1536,1536,12345,24,4.0,"flux2_hq")))
print("OK")
