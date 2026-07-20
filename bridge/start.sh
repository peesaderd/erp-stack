#!/bin/bash
# Start the ERP Internal Bridge Service
# Usage: ./start.sh [port]

PORT=${1:-51516}
cd "$(dirname "$0")"
python3 bridge.py --port "$PORT"
