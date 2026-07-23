"""
LLM Inference — ใช้ Cloudflare Workers AI (Llama 3.3 70B) ฟรี
Fallback ไป Gemini 2.5 Flash
"""
import os
import json
from typing import AsyncGenerator
import httpx
from dotenv import load_dotenv

load_dotenv()

# Cloudflare AI
CF_TOKEN = os.getenv("CLOUDFLARE_AI_TOKEN")
CF_ACCOUNT = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CF_MODEL = os.getenv("CLOUDFLARE_LLM_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
CF_BASE = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run"

# Gemini fallback
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = """คุณคือผู้ช่วย AI สำหรับไลฟ์สตรีม พูดคุยกับผู้ชมสด
ตอบคำถามโดยใช้ข้อมูลจากความรู้ที่มีให้
- ตอบสั้น กระชับ เป็นธรรมชาติ เหมือนพูดในไลฟ์
- ถ้าตอบไม่ได้ บอกว่า "ขอตรวจสอบก่อนนะครับ" อย่างสุภาพ
- ใช้ภาษาไทยหรืออังกฤษตามที่ผู้ชมถาม
- ตอบแบบเป็นกันเอง ไม่ทางการเกินไป"""


def _build_prompt(context: str, question: str, chat_history: list = None) -> str:
    """Build full prompt with RAG context."""
    history_text = ""
    if chat_history:
        history_text = "\n".join([
            f"{'ผู้ชม' if i % 2 == 0 else 'AI'}: {m}"
            for i, m in enumerate(chat_history[-6:])  # last 3 exchanges
        ])
    
    return f"""ข้อมูลอ้างอิง:
{context}

{history_text}

ผู้ชม: {question}
AI:"""


async def ask_cloudflare(
    context: str,
    question: str,
    chat_history: list = None,
) -> str:
    """Ask Cloudflare Workers AI (non-streaming fallback)."""
    prompt = _build_prompt(context, question, chat_history)
    
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{CF_BASE}/{CF_MODEL}",
            headers={"Authorization": f"Bearer {CF_TOKEN}"},
            json={
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ]
            },
        )
        data = resp.json()
        if data.get("success"):
            return data["result"]["response"]
        raise Exception(f"Cloudflare API error: {data}")


async def ask_cloudflare_stream(
    context: str,
    question: str,
    chat_history: list = None,
) -> AsyncGenerator[str, None]:
    """Stream from Cloudflare Workers AI."""
    prompt = _build_prompt(context, question, chat_history)
    
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            f"{CF_BASE}/{CF_MODEL}",
            headers={"Authorization": f"Bearer {CF_TOKEN}"},
            json={
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "stream": True,
            },
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if "response" in data:
                            yield data["response"]
                    except json.JSONDecodeError:
                        continue


async def ask_gemini(
    context: str,
    question: str,
    chat_history: list = None,
) -> str:
    """Fallback: Gemini 2.5 Flash."""
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=GEMINI_KEY)
    
    prompt = _build_prompt(context, question, chat_history)
    full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
    
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=full_prompt,
    )
    return response.text


async def ask(
    context: str,
    question: str,
    chat_history: list = None,
    stream: bool = False,
) -> str | AsyncGenerator[str, None]:
    """Main entry: try Cloudflare first, fallback to Gemini."""
    try:
        if stream:
            return ask_cloudflare_stream(context, question, chat_history)
        return await ask_cloudflare(context, question, chat_history)
    except Exception as e:
        print(f"[LLM] Cloudflare failed: {e}, falling back to Gemini")
        if stream:
            async def _fallback_stream():
                yield await ask_gemini(context, question, chat_history)
            return _fallback_stream()
        return await ask_gemini(context, question, chat_history)
