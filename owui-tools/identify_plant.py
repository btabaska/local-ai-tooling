"""
title: Plant Identifier (BioCLIP 2)
author: btabaska
version: 0.1.1
license: MIT
description: Identify the plant (or any organism) in a chat-attached photo using the local bioclip-api on the rig (BioCLIP 2, TreeOfLife-200M). Fully local, no cloud.
"""

# Canonical source: local-ai-tooling repo owui-tools/identify_plant.py — the OWUI
# DB copy is seeded by scripts/seed-owui-identify-plant.sh (rebuild parity, same
# contract as seed-owui-tool-servers.sh). Edit the repo copy, then re-seed.
#
# Image plumbing (verified against OWUI v0.11.0 backend):
# - UI chats (saved chat_id): process_chat_payload reloads messages from the
#   chat DB, injects attached images into content as image_url parts, then
#   STRIPS message["files"] (middleware.py `message.pop("files", None)`) —
#   all BEFORE tools receive __messages__. So for every UI chat the image is
#   ONLY findable as a {"type": "image_url"} content part (data: URI or an
#   /api/v1/files/<id>/content route).
# - Raw API callers (no saved chat): messages pass through untouched, so
#   images arrive in __messages__[*]["files"] with type=="image" (or
#   content_type image/*), and __files__ carries the chat-level file records
#   ({"file": {"id": ...}}). Both shapes must be scanned.
# - Tools run in-process, so /api/v1/files urls are resolved straight through
#   open_webui.models.files.Files (async in 0.11) + Storage — no HTTP hop, no
#   auth token needed.

import base64
import re

import httpx
from pydantic import BaseModel, Field


def _candidate_urls(messages: list, files: list):
    """Newest-first image URLs/ids from the chat messages, then chat files."""
    for message in reversed(messages or []):
        for f in message.get("files", []) or []:
            if not isinstance(f, dict):
                continue
            is_image = f.get("type") == "image" or str(
                f.get("content_type", "")
            ).startswith("image/")
            if is_image and f.get("url"):
                yield f["url"]
        # UI chats carry images ONLY as image_url content parts (the backend
        # strips message["files"] before tools see __messages__ — see header).
        content = message.get("content")
        if isinstance(content, list):
            for part in reversed(content):
                if isinstance(part, dict) and part.get("type") == "image_url":
                    url = (part.get("image_url") or {}).get("url")
                    if url:
                        yield url
    untyped = []
    for f in reversed(files or []):
        if not isinstance(f, dict):
            continue
        rec = f.get("file") or {}
        content_type = str(
            (rec.get("meta") or {}).get("content_type", "")
            or f.get("content_type", "")
        )
        fid = rec.get("id") or f.get("id")
        if f.get("type") == "image" or content_type.startswith("image/"):
            if f.get("url"):
                yield f["url"]
            if fid:
                yield f"/api/v1/files/{fid}/content"
        elif fid and not content_type:
            # API-driven chats attach bare {"type": "file", "id": ...} records
            # with no mime info — try them last; bioclip 422s non-images.
            untyped.append(f"/api/v1/files/{fid}/content")
    yield from untyped


async def _fetch_bytes(url: str):
    if url.startswith("data:"):
        try:
            return base64.b64decode(url.split(",", 1)[1])
        except Exception:
            return None
    m = re.search(r"/api/v1/files/([0-9a-fA-F-]+)", url)
    if m:
        try:
            from open_webui.models.files import Files
            from open_webui.storage.provider import Storage

            record = await Files.get_file_by_id(m.group(1))
            if record and record.path:
                path = record.path
                try:
                    path = Storage.get_file(path)
                except Exception:
                    pass
                with open(path, "rb") as fh:
                    return fh.read()
        except Exception:
            return None
    if url.startswith("http://") or url.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
        except Exception:
            return None
    return None


class Tools:
    class Valves(BaseModel):
        BIOCLIP_URL: str = Field(
            default="http://bioclip-api:8199",
            description="Base URL of the bioclip-api service (compose-internal).",
        )
        TOP_K: int = Field(default=5, description="How many ranked candidates to return.")
        TIMEOUT_SECONDS: int = Field(
            default=120,
            description="Identify-call timeout (CPU inference ~1s warm, ~30s cold model load).",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def identify_plant(
        self,
        rank: str = "species",
        __messages__: list = [],
        __files__: list = [],
    ) -> str:
        """
        Identify the plant (or animal/fungus/any organism) shown in the photo the
        user attached to this chat, using the local BioCLIP 2 model. The user must
        attach an image to the conversation first — this tool finds the most recent
        attached image automatically; there is no image argument to pass.

        :param rank: Taxonomic rank to classify at: species (default), genus, family, order, class, phylum, or kingdom. Use genus or family when the user wants a coarser answer.
        :return: Ranked candidate taxa with confidence scores and full taxonomy.
        """
        image = None
        for url in _candidate_urls(__messages__, __files__):
            image = await _fetch_bytes(url)
            if image:
                break
        if not image:
            return (
                "No attached image found in this chat. Ask the user to attach a "
                "photo of the plant (paperclip/image button) and call this tool again."
            )

        params = {"k": self.valves.TOP_K, "rank": rank.lower().strip() or "species"}
        try:
            async with httpx.AsyncClient(timeout=self.valves.TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    f"{self.valves.BIOCLIP_URL.rstrip('/')}/identify",
                    params=params,
                    files={"file": ("photo.jpg", image, "image/jpeg")},
                )
                resp.raise_for_status()
                result = resp.json()
        except httpx.HTTPStatusError as exc:
            return f"bioclip-api rejected the image ({exc.response.status_code}): {exc.response.text[:300]}"
        except Exception as exc:
            return f"bioclip-api unreachable at {self.valves.BIOCLIP_URL}: {exc}"

        lines = [
            f"BioCLIP 2 (local, TreeOfLife-200M) — top {len(result.get('predictions', []))} at rank {result.get('rank')}:"
        ]
        for i, p in enumerate(result.get("predictions", []), 1):
            name = p.get(result.get("rank"), "") or p.get("species", "")
            common = f" ({p['common_name']})" if p.get("common_name") else ""
            taxonomy = " > ".join(
                filter(
                    None,
                    [p.get("kingdom"), p.get("phylum"), p.get("class"),
                     p.get("order"), p.get("family"), p.get("genus")],
                )
            )
            lines.append(
                f"{i}. {name}{common} — confidence {p.get('score', 0):.1%} [{taxonomy}]"
            )
        lines.append(
            "Present the top match with its common name and confidence; mention "
            "runners-up only if scores are close. Scores are softmax over ~925k "
            "taxa, so even ~20% on the top hit is a confident call. If the user "
            "asked about toxicity/edibility, add that species-level confusion "
            "between lookalikes is possible and advise caution."
        )
        return "\n".join(lines)
