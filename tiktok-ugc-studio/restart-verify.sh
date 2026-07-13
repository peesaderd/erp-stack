#!/bin/bash
echo "=== Restarting tiktok-ugc-studio ==="
pm2 restart tiktok-ugc-studio
sleep 3
echo ""
echo "=== Health Check ==="
curl -s http://localhost:8105/health
echo ""
echo ""
echo "=== Test Script Generation ==="
curl -s -X POST http://localhost:8105/ugc/scripts/generate \
  -H "Content-Type: application/json" \
  -d '{"product_title":"OUKEYA BLINK BLINK BLUSH","product_details":"Matte liquid lipstick, long-lasting, vibrant color","duration":"8s","tone":"casual","cta":"link in bio"}' | python3 -m json.tool 2>/dev/null || curl -s -X POST http://localhost:8105/ugc/scripts/generate \
  -H "Content-Type: application/json" \
  -d '{"product_title":"OUKEYA BLINK BLINK BLUSH","product_details":"Matte liquid lipstick","duration":"8s"}'
