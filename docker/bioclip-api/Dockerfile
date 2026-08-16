FROM python:3.12-slim

# CPU-only torch wheels keep the image ~1.5GB (vs ~8GB CUDA) and avoid VRAM
# contention: the 3090 Ti is fully budgeted for llama-swap (22GB+ resident LLM),
# so BioCLIP runs on CPU (~2-5s/image for ViT-L/14). GPU mode = rebuild without
# the CPU index below, set BIOCLIP_DEVICE=cuda and add a gpus: reservation.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir pybioclip==2.1.6 "fastapi<0.116" "uvicorn<0.31" python-multipart

WORKDIR /app
COPY app.py /app/app.py

# HF weight cache lives on the bioclip_data volume — ~2GB downloaded on first
# predict, fully offline afterwards.
ENV HF_HOME=/data/hf

EXPOSE 8199
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8199"]
