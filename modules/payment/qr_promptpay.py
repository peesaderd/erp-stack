"""
PromptPay QR Generator — ตัวสร้าง EMVCo QR Payload + รูป QR PNG

SSOT ของเลข PromptPay ของร้าน (PROMPTPAY_ID / SLIPOK_RECEIVER_ID)
อ่านจาก env กลาง: PROMPTPAY_ID (ค่า default "0993946144" ตาม POS เดิม)
ย้ายมาจาก super-appsheet/src/payment_api.py ให้ทุกโปรเจกต์ใช้ร่วมกัน (single source)

ใช้ร่วมกับ slipok_client.py (ตรวจยอด) + payment_client.py (เขียน payment_transaction) ใน modules/payment
"""

import io
import os
import base64

DEFAULT_PROMPTPAY_ID = "0993946144"


def promptpay_id() -> str:
    """PromptPay ID ของร้าน (SSOT). อ่านจาก env PROMPTPAY_ID."""
    return (os.environ.get("PROMPTPAY_ID") or DEFAULT_PROMPTPAY_ID).strip()


def crc16_ccitt(data: str) -> str:
    """Pure-Python CRC16-CCITT (0x1021) for EMVCo QR."""
    crc = 0xFFFF
    for byte in data.encode("ascii"):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def generate_promptpay_payload(merchant_id: str, amount: float | None = None) -> str:
    """Generate EMVCo QR Payload for PromptPay (Standard)."""
    merchant_id = merchant_id.strip()
    if len(merchant_id) == 10 and merchant_id.isdigit():
        # Mobile: 0XX-XXX-XXXX -> 0066XXXXXXXX
        merchant_id = "0066" + merchant_id[1:]
        mid_len = len(merchant_id)
        merchant_account = f"0016A00000067701011101{mid_len:02d}{merchant_id}"
    elif len(merchant_id) == 13 and merchant_id.isdigit():
        # National ID / Tax ID
        mid_len = len(merchant_id)
        merchant_account = f"0016A00000067701011102{mid_len:02d}{merchant_id}"
    elif len(merchant_id) == 15 and merchant_id.isdigit():
        # e-Wallet ID
        mid_len = len(merchant_id)
        merchant_account = f"0016A00000067701011103{mid_len:02d}{merchant_id}"
    else:
        raise ValueError(f"Invalid PromptPay ID: {merchant_id}")

    payload = f"000201{len(merchant_account):02d}{merchant_account}5303764"
    if amount is not None:
        amt_str = f"{amount:.2f}"
        payload += f"54{len(amt_str):02d}{amt_str}"
    payload += "5802TH6304"
    payload += crc16_ccitt(payload)
    return payload


def generate_qr_png(payload: str, box_size: int = 10, border: int = 4) -> bytes:
    """Render EMVCo payload into a PNG image (bytes)."""
    import qrcode as qrcode_mod

    qr = qrcode_mod.QRCode(
        version=None,
        error_correction=qrcode_mod.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_qr(amount: float | None = None, box_size: int = 10, border: int = 4) -> dict:
    """Convenience: build PromptPay QR from the store's SSOT PROMPTPAY_ID.
    Returns { payload, base64_png, amount, promptpay_id }."""
    pid = promptpay_id()
    payload = generate_promptpay_payload(pid, amount)
    png = generate_qr_png(payload, box_size, border)
    return {
        "payload": payload,
        "base64_png": base64.b64encode(png).decode(),
        "amount": amount,
        "promptpay_id": pid,
    }
