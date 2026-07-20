"""
Pipeline Config — จุดเดียวที่เก็บ default duration & settings
แก้ที่นี่ที่เดียว ทุก module ที่เกี่ยวข้องจะใช้ค่าจากนี้
"""

# ─── Duration Settings ────────────────────────────────────────────
# Default duration (วินาที) ถ้า frontend ไม่ส่งค่ามา
DEFAULT_DURATION = 8

# Allowed durations ที่ WebUI มีให้เลือก
ALLOWED_DURATIONS = [8, 15]

# Max duration ที่ Prodia Wan 2.7 รองรับ
MAX_WAN_DURATION = 15
