# Backend image (FastAPI + local embedding/rerank models). Build context: repo root.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HOME=/models
WORKDIR /app

# CPU-only torch first (the default Linux wheel drags in several GB of CUDA libraries).
RUN pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Bake the two models into the image so cold starts don't download them.
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('BAAI/bge-small-en-v1.5'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

COPY backend/app ./app

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
