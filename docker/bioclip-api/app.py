"""bioclip-api — BioCLIP 2 species identification behind a thin FastAPI.

Consumer: the Open WebUI `identify_plant` workspace tool (and anything else on
the LAN that can POST an image). The classifier is lazy-loaded on the first
/identify call so /health stays instant for container healthchecks; the first
call on a fresh volume also downloads ~2GB of weights from Hugging Face.
"""

import os
import tempfile

from bioclip import Rank, TreeOfLifeClassifier
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

DEVICE = os.environ.get("BIOCLIP_DEVICE", "cpu")

app = FastAPI(title="bioclip-api")
_classifier = None


def classifier() -> TreeOfLifeClassifier:
    global _classifier
    if _classifier is None:
        _classifier = TreeOfLifeClassifier(device=DEVICE)
    return _classifier


@app.get("/health")
def health():
    return {"status": "ok", "device": DEVICE, "model_loaded": _classifier is not None}


@app.post("/identify")
async def identify(
    file: UploadFile = File(...),
    k: int = Query(5, ge=1, le=25),
    rank: str = Query("species"),
):
    try:
        target_rank = Rank[rank.upper()]
    except KeyError:
        valid = ", ".join(r.name.lower() for r in Rank)
        raise HTTPException(422, f"rank must be one of: {valid}")

    data = await file.read()
    if not data:
        raise HTTPException(422, "empty upload")

    # pybioclip's stable public API takes file paths, not bytes/PIL across
    # versions — round-trip through a temp file.
    suffix = os.path.splitext(file.filename or "")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        preds = classifier().predict(path, rank=target_rank, k=k)
    except Exception as exc:  # torch/PIL decode errors -> client-visible 422
        raise HTTPException(422, f"could not classify image: {exc}")
    finally:
        os.unlink(path)

    for p in preds:
        p.pop("file_name", None)

    return {
        "model": "BioCLIP 2 (TreeOfLife-200M)",
        "device": DEVICE,
        "rank": target_rank.name.lower(),
        "predictions": preds,
    }
