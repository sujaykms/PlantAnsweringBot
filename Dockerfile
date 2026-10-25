# syntax=docker/dockerfile:1
# All-in-one image: Next.js frontend + FastAPI backend + Postgres/pgvector (documents pre-loaded).
# One public port ($PORT, default 7860). Build context: repo root.

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV BACKEND_URL=http://127.0.0.1:8000 NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM pgvector/pgvector:pg16
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models UV_PYTHON_INSTALL_DIR=/opt/python UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=web /usr/local/bin/node /usr/local/bin/node

# Python 3.12 venv with CPU-only torch (the default Linux wheel pulls several GB of CUDA libraries).
RUN uv venv --python 3.12 /opt/venv
ENV VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH PYTHONPATH=/app/backend
RUN uv pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt /tmp/requirements.txt
RUN uv pip install -r /tmp/requirements.txt

# Bake the two models into the image so cold starts don't download them.
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('BAAI/bge-small-en-v1.5'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

COPY backend/app /app/backend/app
COPY backend/ingest /app/backend/ingest
COPY backend/scripts /app/backend/scripts
COPY db /app/db
COPY docs /app/docs
COPY --from=web /web/.next/standalone /app/web
COPY --from=web /web/.next/static /app/web/.next/static
COPY --from=web /web/public /app/web/public
COPY docker /app/docker

# Hugging Face Spaces runs containers as uid 1000, so do everything as that user.
RUN useradd -m -u 1000 user && mkdir -p /seed && chown -R user:user /seed /app
USER user
# Create + migrate + ingest the database at build time; the entrypoint copies it to a fresh data dir.
RUN bash /app/docker/seed.sh

# Models are baked in, so never call the Hub at runtime.
ENV HF_HUB_OFFLINE=1

# Defaults mirror the local setup; override with platform variables. OPENROUTER_API_KEY is required.
ENV PORT=7860 ROUTER_MODEL=qwen/qwen-2.5-7b-instruct GUARD_MODEL=google/gemini-2.5-flash-lite \
    ANSWER_MODEL=openai/gpt-4.1-mini
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD curl -fs http://127.0.0.1:${PORT}/api/health || exit 1
# Replace the base image's postgres entrypoint with ours.
ENTRYPOINT ["bash", "/app/docker/entrypoint.sh"]
