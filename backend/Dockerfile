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

COPY . .

RUN mkdir -p storage/pdfs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
