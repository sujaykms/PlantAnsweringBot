#!/usr/bin/env bash
# Assemble a Hugging Face Space repo (Docker SDK) from this project: scripts/prepare_space.sh <output-dir>
set -euo pipefail
OUT="${1:?usage: prepare_space.sh <output-dir>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$OUT"
for item in Dockerfile Dockerfile.dockerignore backend frontend db docs docker; do
  rsync -a --delete \
    --exclude '.git' --exclude '.env' --exclude '.env.local' --exclude 'node_modules' --exclude '.next' \
    --exclude '.venv' --exclude '__pycache__' --exclude 'tests' \
    "$ROOT/$item" "$OUT/"
done
cp "$ROOT/huggingface/README.md" "$OUT/README.md"
echo "Space files ready in $OUT"
