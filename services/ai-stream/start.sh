#!/bin/bash
# AI Live Stream — Start all services
# Usage: ./start.sh [dev|prod]

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

MODE="${1:-prod}"

echo "🚀 AI Live Stream — Starting ($MODE mode)"

# 1. Start SRS (RTMP + HLS)
echo "[1/3] Starting SRS streaming server..."
docker compose up -d srs
sleep 2

# 2. Start Python backend
echo "[2/3] Starting AI Backend (port 8150)..."
if [ "$MODE" = "dev" ]; then
    python3 server.py &
    echo "  PID: $!"
else
    # Production with nohup
    nohup python3 server.py > data/server.log 2>&1 &
    echo "  PID: $! (log: data/server.log)"
fi

sleep 2

# 3. Verify
echo "[3/3] Verifying services..."
curl -sf http://localhost:8150/api/health > /dev/null && echo "  ✅ AI Backend: OK" || echo "  ❌ AI Backend: FAIL"
curl -sf http://localhost:1987/api/v1/versions > /dev/null 2>&1 && echo "  ✅ SRS Server: OK" || echo "  ❌ SRS Server: FAIL"

echo ""
echo "🎯 Stream Key for OBS: rtmp://localhost:1935/live/stream"
echo "🌐 Player: http://localhost:8083/players/ (or your domain)"
echo "📋 Overlay (OBS): http://localhost:8150/overlay"
echo ""
echo "✨ Done!"
