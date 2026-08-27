"""
SlipOK Client — ตรวจสอบสลิป/ยอดเงินเข้าจริง (verify payslip via SlipOK API)

Docs: SlipOK_API_Guide v1.13 (2026-02-28) — พี่ให้ docs + API key (Branch ID 74705)
Endpoint ตรวจสลิป:
  POST https://api.slipok.com/api/line/apikey/<BRANCH_ID>
  Header: { x-authorization: <API_KEY> }
  Body (อย่างใดอย่างหนึ่ง): { data } | { files } | { url }
    + optional { log: boolean } (true = ตรวจบัญชีผู้รับ + กันสลิปซ้ำ, คิดโควต้าเฉพาะสลิปถูกต้อง+ตรงบัญชี)
    + optional { amount: number } (เช็คยอดในสลิปตรง)
Endpoint โควตา:
  GET https://api.slipok.com/api/line/apikey/<BRANCH_ID>/quota

แบรนช์/คีย์จาก .env (SLIPOK_BRANCH_ID, SLIPOK_API_KEY) ไม่ฝังค่าในโค้ด
โต้ตอบกับ payment_client (modules/payment) เขียนธุรกรรมลง schema payment_transaction กลาง
"""

import os
import re
from typing import Optional

import urllib.request
import urllib.parse
import urllib.error
import json
import base64
import uuid

API_BASE = "https://api.slipok.com/api/line/apikey"

# Bank code ตาม docs
BANK_CODE = {
    "002": "BBL", "004": "KBANK", "006": "KTB", "011": "TTB", "014": "SCB",
    "025": "BAY", "069": "KKP", "022": "CIMBT", "067": "TISCO", "024": "UOBT",
    "071": "TCD",
}


class SlipOKError(Exception):
    """Base error for SlipOK client."""

    def __init__(self, message: str, code: int = None, raw=None):
        super().__init__(message)
        self.code = code  # รหัส error จาก SlipOK (เช่น 1012 สลิปซ้ำ)
        self.raw = raw


def _branch_id() -> str:
    val = os.environ.get("SLIPOK_BRANCH_ID") or ""
    if not val:
        raise SlipOKError("SLIPOK_BRANCH_ID not set")
    return val


def _api_key() -> str:
    val = os.environ.get("SLIPOK_API_KEY") or ""
    if not val:
        raise SlipOKError("SLIPOK_API_KEY not set")
    return val


def _request(method: str, path: str, body_bytes: Optional[bytes] = None,
             content_type: str = "application/json") -> dict:
    """Call SlipOK API with x-authorization header."""
    url = f"{API_BASE}/{_branch_id()}/{path}" if path else f"{API_BASE}/{_branch_id()}"
    # กัน path ซ้ำ
    if path and url.rstrip("/").endswith(f"/{path}".lstrip("/")):
        pass
    req = urllib.request.Request(
        url, data=body_bytes,
        headers={
            "x-authorization": _api_key(),
            "Content-Type": content_type,
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        summary = raw[:400]
        # พยายามดึง error code จาก response
        code = None
        try:
            j = json.loads(raw)
            code = j.get("code") or (j.get("data") or {}).get("code")
        except Exception:
            pass
        raise SlipOKError(f"SlipOK {method} {url} -> {e.code}: {summary}", code=code, raw=raw)
    except (urllib.error.URLError, ConnectionError) as e:
        raise SlipOKError(f"SlipOK unreachable: {e}")


def check_quota() -> dict:
    """GET quota. Returns data dict {quota, overQuota, specialQuota, endDate, specialEndDate}."""
    res = _request("GET", "quota")
    return res.get("data", {})


def _build_body(payment_data: Optional[str] = None, file_upload=None,
                url: Optional[str] = None, log: bool = True,
                amount: Optional[float] = None) -> tuple:
    """Build request body. Returns (body, content_type)."""
    provided = [bool(payment_data), bool(file_upload), bool(url)]
    if sum(int(b) for b in provided) != 1:
        raise SlipOKError("Must supply exactly one of: data | files | url")
    if payment_data:
        payload = {"data": payment_data}
    elif file_upload:
        # file_upload: (filename, bytes, mimetype)
        filename, content, mimetype = file_upload
        boundary = "----SlipOK" + uuid.uuid4().hex
        body = _multipart(boundary, {"files": (filename, content, mimetype)})
        return (body, f"multipart/form-data; boundary={boundary}")
    else:
        payload = {"url": url}
    if log:
        payload["log"] = True
    if amount is not None:
        payload["amount"] = amount
    return (json.dumps(payload).encode("utf-8"), "application/json")


def _multipart(boundary: str, fields: dict) -> bytes:
    """Encode multipart/form-data for a single file field."""
    parts = []
    for name, (filename, content, mimetype) in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
        parts.append(f"Content-Type: {mimetype}\r\n\r\n".encode())
        parts.append(content)
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts)


def verify_slip(payment_data: Optional[str] = None, file_upload=None,
                url: Optional[str] = None, log: bool = True,
                amount: Optional[float] = None,
                expected_receiver_account: Optional[str] = None,
                expected_receiver_proxy: Optional[str] = None) -> dict:
    """Check (verify) a payslip via SlipOK.

    Returns normalized dict:
      { verified, trans_ref, amount, bank, receiving_bank, sender_bank, date, time,
        sender, receiver, proxy, account, ref1, raw }
    Raises SlipOKError on failure (unsuccessful / signature fail / network).
    """
    body, ctype = _build_body(payment_data, file_upload, url, log, amount)
    res = _request("POST", "", body, ctype)
    ok = res.get("success")
    data = res.get("data") or {}
    if not ok or not data.get("success"):
        msg = data.get("message") or res.get("message") or "verification failed"
        code = data.get("code")
        raise SlipOKError(msg, code=code, raw=res)

    # Normalize
    sender = data.get("sender") or {}
    receiver = data.get("receiver") or {}
    out = {
        "verified": True,
        "message": data.get("message"),
        "language": data.get("language"),
        "trans_ref": data.get("transRef"),
        "amount": data.get("amount"),
        "paid_local_amount": data.get("paidLocalAmount"),
        "paid_local_currency": data.get("paidLocalCurrency"),
        "country_code": data.get("countryCode"),
        "trans_date": data.get("transDate"),
        "trans_time": data.get("transTime"),
        "trans_timestamp": data.get("transTimestamp"),
        "trans_fee": data.get("transFeeAmount"),
        "ref1": data.get("ref1"),
        "ref2": data.get("ref2"),
        "ref3": data.get("ref3"),
        "to_merchant_id": data.get("toMerchantId"),
        "receiving_bank": data.get("receivingBank"),
        "receiving_bank_name": BANK_CODE.get(data.get("receivingBank"), data.get("receivingBank")),
        "sending_bank": data.get("sendingBank"),
        "sending_bank_name": BANK_CODE.get(data.get("sendingBank"), data.get("sendingBank")),
        "sender": sender,
        "receiver": receiver,
        "sender_display_name": sender.get("displayName"),
        "receiver_display_name": receiver.get("displayName"),
        "raw": data,
    }

    # ตรวจบัญชีผู้รับ (ถ้าระบุ) ตาม docs: normalize เลขโดยตัดตัวที่ไม่ใช่เลข/x/X
    if expected_receiver_account or expected_receiver_proxy:
        _assert_receiver_match(out, expected_receiver_account, expected_receiver_proxy)
    return out


def _digits_and_mask(value: str) -> str:
    """Keep only digits and x/X (docs normalization for masked account)."""
    return re.sub(r"[^0-9xX]", "", value or "")


def _assert_receiver_match(out: dict, expected_account: Optional[str],
                           expected_proxy: Optional[str]) -> None:
    """Verify receiver account matches expected (masked partial match per docs)."""
    receiver = out.get("receiver") or {}
    account_val = (receiver.get("account") or {}).get("value")
    proxy_val = (receiver.get("proxy") or {}).get("value")
    if expected_account:
        exp = _digits_and_mask(expected_account)
        got = _digits_and_mask(account_val)
        if exp and got and not _partial_match(exp, got):
            raise SlipOKError("Receiver account does not match expected")
    if expected_proxy:
        exp = _digits_and_mask(expected_proxy)
        got = _digits_and_mask(proxy_val)
        if exp and got and not _partial_match(exp, got):
            raise SlipOKError("Receiver proxy does not match expected")


def _partial_match(exp: str, got: str) -> bool:
    """Match masked form, e.g. exp '9999991234' vs got 'XXX-X-XX123-4'."""
    if len(exp) != len(got):
        return False
    for e, g in zip(exp, got):
        if e != g:
            return False
    return True
