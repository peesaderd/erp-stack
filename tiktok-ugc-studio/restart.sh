#!/bin/bash
echo "=== Restarting tiktok-ugc-studio ==="
pm2 restart tiktok-ugc-studio
sleep 3
echo "=== Health ==="
curl -s http://localhost:8105/health
echo ""
echo "=== Script Test ==="
curl -s -X POST http://localhost:8105/ugc/scripts/generate \
  -H "Content-Type: application/json" \
  -d '{"product_title":"OUKEYA BLUSH","duration":"8s"}'
echo ""
