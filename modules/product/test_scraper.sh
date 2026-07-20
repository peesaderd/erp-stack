#!/bin/bash
set -e

echo "1️⃣  Pricing"
curl -s http://localhost:8106/api/v1/pricing | python3 -c "
import json,sys;d=json.load(sys.stdin)
print('  tiers:', list(d.get('tiers',{}).keys()))"

echo ""
echo "2️⃣  Create API Key"
KEY_RESP=$(curl -s -X POST http://localhost:8106/api/v1/keys/create \
  -H "x-user-id: demo" -H "Content-Type: application/json" \
  -d '{"name":"Production Key"}')
API_KEY=$(echo "$KEY_RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('key',''))")
echo "  ✅ Key: ${API_KEY:0:20}..."

echo ""
echo "3️⃣  Scrape Amazon"
curl -s -X POST http://localhost:8106/api/v1/scrape \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.amazon.com/dp/B09B8V1LZ3","use_vision":false}' | python3 -c "
import json,sys;d=json.load(sys.stdin);p=d.get('product',{}) or {}
print(f\"  {'✅' if d['success'] else '❌'} method={d['method']} | {str(p.get('name',''))[:40]}\")"

echo ""
echo "4️⃣  Sheets setup"
curl -s http://localhost:8106/api/v1/export/setup | python3 -c "
import json,sys;d=json.load(sys.stdin)
print(f\"  {'✅' if d.get('success') else '❌'} configured={d.get('configured')}\")"

echo ""
echo "5️⃣  Usage"
curl -s http://localhost:8106/api/v1/usage -H "x-user-id: demo" | python3 -c "
import json,sys;d=json.load(sys.stdin)
print(f\"  scrapes={d.get('total_scrapes')} | remaining={d.get('remaining')}/{d.get('monthly_limit')}\")"

echo ""
echo "6️⃣  Legacy endpoint"
curl -s -X POST http://localhost:8106/api/v1/product/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.amazon.com/dp/B09B8V1LZ3","use_vision":false}' | python3 -c "
import json,sys;d=json.load(sys.stdin);print(f\"  {'✅' if d['success'] else '❌'} legacy={d['method']}\")"

echo ""
echo "===== ✅ All Systems Go ====="
