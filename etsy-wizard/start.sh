#!/bin/bash
cd /home/openhands/erp-stack/etsy-wizard

# Activate venv if exists, else use system
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Ensure packages
pip install anyio httpx starlette fastapi uvicorn python-multipart --quiet 2>/dev/null

python3 -m uvicorn main:app --host 0.0.0.0 --port 8104 --reload --root-path /etsy
