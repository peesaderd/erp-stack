#!/bin/bash
export PORT="${PRODIA_PORT:-8112}"
export PRODIA_API_KEY="${PRODIA_API_KEY:-}"
cd /home/openhands/erp-stack
exec python3 -m uvicorn prodia-image-service:app --host 0.0.0.0 --port "$PORT"
