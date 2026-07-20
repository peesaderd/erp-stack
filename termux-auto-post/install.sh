#!/bin/bash
"""
install.sh — ติดตั้ง Termux Auto Post บนมือถือ

วิธีใช้:
  # บน Termux:
  pkg install git python3
  git clone https://github.com/YOUR_USER/erp-stack.git
  cd erp-stack/termux-auto-post
  bash install.sh
"""

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  📱 Termux Auto Post — Installer        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Install system dependencies (Termux)
echo "📦 Installing system libraries..."
pkg install libjpeg-turbo libpng freetype -y 2>/dev/null || echo "⚠️  Skip system packages (not Termux)"

# Install dependencies
echo "📦 Installing Python packages..."
pip install -r requirements.txt

# Fallback: ถ้า Pillow build ไม่ผ่าน
if [ $? -ne 0 ]; then
    echo "⚠️  Pillow failed — installing core packages only..."
    pip install requests schedule rich python-dotenv
fi

# Create directories
echo "📁 Creating directories..."
mkdir -p cookies cache media logs

# Copy config
if [ ! -f config.json ]; then
    echo "📝 Copying config.example.json → config.json"
    cp config.example.json config.json
    echo "⚠️  อย่าลืมแก้ไฟล์ config.json!"
fi

# Test import
echo ""
echo "🧪 Testing imports..."
python3 -c "
from platforms.tiktok import TikTok
from platforms.facebook import Facebook
from platforms.instagram import Instagram
from platforms.twitter_x import TwitterX
from platforms.threads import Threads
from platforms.shopee import Shopee
print('✅ All platform modules loaded successfully')
"

echo ""
echo "✅ Install complete!"
echo ""
echo "📋 ขั้นตอนต่อไป:"
echo "  1. nano config.json     ← แก้ไข API keys"
echo "  2. python3 termux_main.py --setup"
echo "  3. python3 termux_main.py --post --all  ← ทดสอบ"
echo "  4. python3 termux_main.py --schedule     ← รันจริง"
echo ""
echo "💡 อย่าลืม: termux-wake-lock (กันเครื่องหลับ)"
echo ""
