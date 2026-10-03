# Match the local dev venv (3.10): requirements.txt was frozen there and
# pins 3.10-only backports such as backports.asyncio.runner.
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# CPU-only torch wheel: the VM has no GPU, and the default PyPI wheel
# drags in several GB of CUDA libraries.
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# services/config.py forces HF_HUB_OFFLINE=1 at runtime, so the embedding
# model has to be in the image's HF cache already. Keep in sync with
# EMBEDDING_MODEL in deploy/docker-compose.yml.
ARG EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
RUN HF_HUB_OFFLINE=0 python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

COPY . .

RUN mkdir -p storage/pdfs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Behind nginx, request.client.host would be nginx's container IP for every
# request, so services/rate_limit.py's per-IP limits would be shared by all
# users. Trust X-Forwarded-For from nginx (which overwrites it with
# $remote_addr); port 8000 is not published, so only nginx can reach this.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
