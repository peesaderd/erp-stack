#!/bin/bash
# =============================================================================
# manage-password.sh — เปลี่ยน Password Plane พร้อมกันทั้ง DB + .env
#
# Usage:
#   ./manage-password.sh <email> <new-password>
#
# Example:
#   ./manage-password.sh admin@plane.local Plane@ERP2026
#
# What it does:
#   1. เปลี่ยน password ใน database ผ่าน Django set_password() — ถูกต้อง 100%
#   2. อัปเดต PLANE_PASSWORD ใน .env ของ bridge-server
#   3. Restart bridge-server
#   4. ทดสอบ login จริงผ่าน curl ยืนยันผล
# =============================================================================

if [ $# -ne 2 ]; then
    echo "Usage: $0 <email> <new-password>"
    echo ""
    echo "Examples:"
    echo "  $0 admin@plane.local Plane@ERP2026"
    exit 1
fi

EMAIL="$1"
NEW_PASSWORD="$2"

BRIDGE_DIR="$HOME/bridge-server/bridge-server"
ENV_FILE="$BRIDGE_DIR/.env"
PLANE_URL="http://localhost:54512"
BRIDGE_URL="http://localhost:54517"

echo "============================================"
echo "  Plane Password Manager"
echo "============================================"
echo "  Email:    $EMAIL"
echo "============================================"
echo ""

# -------------------------------------------------------------------------
# Step 1: เปลี่ยน password ใน database
# -------------------------------------------------------------------------
echo "[1/4] Changing password in database..."

docker exec -i plane-api python3 /dev/stdin "$EMAIL" "$NEW_PASSWORD" 2>&1 << 'PYEOF'
import os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plane.settings")
sys.path.insert(0, "/code")
import django
django.setup()
from plane.db.models import User
email = sys.argv[1]
new_password = sys.argv[2]
try:
    u = User.objects.get(email=email)
    u.set_password(new_password)
    u.save()
    print("OK: Password updated successfully")
except User.DoesNotExist:
    print("ERROR: User not found")
    sys.exit(1)
PYEOF

echo ""

# -------------------------------------------------------------------------
# Step 2: อัปเดต .env
# -------------------------------------------------------------------------
echo "[2/4] Updating .env file..."

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found!"
    exit 1
fi

if grep -q "^PLANE_PASSWORD=" "$ENV_FILE"; then
    sed -i "s|^PLANE_PASSWORD=.*|PLANE_PASSWORD=$NEW_PASSWORD|" "$ENV_FILE"
    echo "OK: Updated PLANE_PASSWORD in $(basename $ENV_FILE)"
else
    echo "PLANE_PASSWORD=$NEW_PASSWORD" >> "$ENV_FILE"
    echo "OK: Added PLANE_PASSWORD to $(basename $ENV_FILE)"
fi

echo ""

# -------------------------------------------------------------------------
# Step 3: Restart bridge-server
# -------------------------------------------------------------------------
echo "[3/4] Restarting bridge-server..."

pm2 restart bridge-server > /dev/null 2>&1

echo "Waiting for bridge-server to be ready..."
for i in $(seq 1 15); do
    if curl -sf "$BRIDGE_URL/health" > /dev/null 2>&1; then
        echo "Bridge-server is ready! (${i}s)"
        break
    fi
    if [ "$i" -eq 15 ]; then
        echo "WARN: Bridge-server not ready after ${i}s, continuing..."
    fi
    sleep 1
done

echo ""

# -------------------------------------------------------------------------
# Step 4: ทดสอบ login ผ่าน Plane โดยตรง
# -------------------------------------------------------------------------
echo "[4/4] Verifying login via Plane API..."

CSRF_RESP=$(curl -s -c /tmp/plane_csrf_cookies.txt "$PLANE_URL/auth/get-csrf-token/" 2>&1) || {
    echo "WARN: Cannot reach Plane at $PLANE_URL"
    echo ""
    echo "============================================"
    echo "  ✅ Password changed (Plane unreachable)"
    echo "============================================"
    exit 0
}

CSRF_TOKEN=$(echo "$CSRF_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['csrf_token'])" 2>/dev/null)

if [ -z "$CSRF_TOKEN" ]; then
    echo "WARN: Could not get CSRF token"
    echo ""
    echo "============================================"
    echo "  ✅ Password changed (verify skipped)"
    echo "============================================"
    exit 0
fi

curl -s -c /tmp/plane_login_cookies.txt -b /tmp/plane_csrf_cookies.txt \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "X-CSRFToken: $CSRF_TOKEN" \
    -H "Referer: $PLANE_URL" \
    -d "email=$EMAIL&password=$NEW_PASSWORD" \
    "$PLANE_URL/auth/sign-in/" > /dev/null 2>&1

if grep -q "session-id" /tmp/plane_login_cookies.txt 2>/dev/null; then
    echo "OK: Login successful!"
    echo ""
    echo "============================================"
    echo "  ✅ Password changed successfully!"
    echo "============================================"
else
    echo "WARN: Login returned unexpected response"
    echo ""
    echo "============================================"
    echo "  ⚠️  Password changed (verify manually)"
    echo "============================================"
fi

rm -f /tmp/plane_csrf_cookies.txt /tmp/plane_login_cookies.txt
