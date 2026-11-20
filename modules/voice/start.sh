#!/bin/bash
source /home/openhands/erp-stack/.env
export CF_ACCOUNT_ID=$CLOUDFLARE_ACCOUNT_ID
export CF_WORKERS_AI_TOKEN=$CLOUDFLARE_AI_TOKEN
python3 /home/openhands/erp-stack/modules/voice/voice_gateway.py
