#!/usr/bin/env python3
"""gpu-arbiter — transparent reverse proxy in front of ComfyUI that enforces
TAKE-TURNS GPU sharing with the llama-swap LLM stack on the single RTX 3090 Ti.

The single 24 GB card can't hold a 73k-ctx 24B LLM (~22.8 GiB) AND an image
model at once. This arbiter makes them alternate:
  - POST /prompt  -> force-unload the LLM (llama-swap /api/models/unload, ~182ms)
    BEFORE forwarding, so ComfyUI never loads an image model while 22 GiB of LLM
    is resident (which would OOM the generation).
  - a background watcher polls ComfyUI's /queue; when it drains, it POSTs /free
    to ComfyUI so image VRAM is released and the LLM can reload on the next chat.
  - every other request (incl. the /ws progress websocket) is proxied verbatim.

Frontends (Open WebUI / Lumiverse / Marinara) point their ComfyUI URL at this
arbiter (:8189) instead of ComfyUI (:8188). Runs in the compose network so it
reaches comfyui + llama-swap by service name.
"""
import asyncio, aiohttp
from aiohttp import web, WSMsgType

COMFY = "http://comfyui:8188"
LLAMASWAP_UNLOAD = "http://llama-swap:8080/api/models/unload"
LISTEN_PORT = 8189
HOP = {"host", "content-length", "transfer-encoding", "content-encoding", "connection"}

session: aiohttp.ClientSession = None
_busy = False

async def unload_llm():
    try:
        async with session.post(LLAMASWAP_UNLOAD, timeout=aiohttp.ClientTimeout(total=10)) as r:
            await r.read()
        print("[arbiter] LLM unloaded before generation", flush=True)
    except Exception as e:
        print("[arbiter] unload_llm error:", e, flush=True)

async def free_comfy():
    try:
        async with session.post(COMFY + "/free", json={"unload_models": True, "free_memory": True},
                                timeout=aiohttp.ClientTimeout(total=20)) as r:
            await r.read()
        print("[arbiter] ComfyUI freed (queue drained)", flush=True)
    except Exception as e:
        print("[arbiter] free_comfy error:", e, flush=True)

async def queue_watcher():
    global _busy
    while True:
        try:
            async with session.get(COMFY + "/queue", timeout=aiohttp.ClientTimeout(total=5)) as r:
                q = await r.json()
            active = bool(q.get("queue_running")) or bool(q.get("queue_pending"))
            if active:
                _busy = True
            elif _busy:
                _busy = False
                await free_comfy()
        except Exception:
            pass
        await asyncio.sleep(1)

async def ws_proxy(request):
    client = web.WebSocketResponse()
    await client.prepare(request)
    qs = request.query_string
    url = COMFY.replace("http", "ws") + "/ws" + (("?" + qs) if qs else "")
    try:
        async with session.ws_connect(url) as up:
            async def c2u():
                async for m in client:
                    if m.type == WSMsgType.TEXT: await up.send_str(m.data)
                    elif m.type == WSMsgType.BINARY: await up.send_bytes(m.data)
            async def u2c():
                async for m in up:
                    if m.type == WSMsgType.TEXT: await client.send_str(m.data)
                    elif m.type == WSMsgType.BINARY: await client.send_bytes(m.data)
            await asyncio.gather(c2u(), u2c())
    except Exception as e:
        print("[arbiter] ws error:", e, flush=True)
    return client

async def handler(request):
    print("[arbiter] REQ %s %s" % (request.method, request.raw_path), flush=True)
    if request.path in ("/ws", "/api/ws"):
        return await ws_proxy(request)
    if request.method == "POST" and request.path in ("/prompt", "/api/prompt"):
        await unload_llm()
    body = await request.read()
    url = COMFY + request.raw_path
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP}
    async with session.request(request.method, url, data=body, headers=headers,
                               allow_redirects=False,
                               timeout=aiohttp.ClientTimeout(total=900)) as resp:
        raw = await resp.read()
        out = web.Response(body=raw, status=resp.status)
        for k, v in resp.headers.items():
            if k.lower() not in HOP:
                out.headers[k] = v
        return out

async def on_start(app):
    global session
    session = aiohttp.ClientSession()
    app["w"] = asyncio.create_task(queue_watcher())

async def on_stop(app):
    app["w"].cancel()
    await session.close()

app = web.Application(client_max_size=2 * 1024**3)
app.router.add_route("*", "/{tail:.*}", handler)
app.on_startup.append(on_start)
app.on_cleanup.append(on_stop)
web.run_app(app, port=LISTEN_PORT)
