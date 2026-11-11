#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
npm ci
uv sync --project apps/api
uv sync --project workers/indexer
npm run build:headless -w @athena/playground
docker pull python:3.12-slim
