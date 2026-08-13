"""Voice API Router - Mistral Voxtral + Mistral Large + edge-tts/gTTS"""

import json
import logging
import base64
import os
import io
import os
import tempfile
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from fastapi.responses import Response
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_BASE_URL = "https://api.mistral.ai/v1"

# ── Models ─────────────────────────────────────────────────────────────────

class VoiceProcessRequest(BaseModel):
    text: str
    conversationHistory: list[dict] = []
    session_id: str | None = None

class ChatRequest(BaseModel):
    text: str
    system_prompt: Optional[str] = None
    language: str = "th"

class TTSRequest(BaseModel):
    text: str
    voice: str = "paul"
    mood: str = "neutral"
    language: str = "th"

class TranscribeResponse(BaseModel):
    text: str
    language: str

class ChatResponse(BaseModel):
    text: str
    audio_url: Optional[str] = None

# ── Mistral helpers ─────────────────────────────────────────────────────────

PRESET_VOICES = {
    "paul": {
        "confident": "98559b22-62b5-4a64-a7cd-fc78ca41faa8",
        "neutral": "c69964a6-ab8b-4f8a-9465-ec0925096ec8",
        "happy": "1024d823-a11e-43ee-bf3d-d440dccc0577",
        "cheerful": "01d985cd-5e0c-4457-bfd8-80ba31a5bc03",
        "exciting": "5940190b-f58a-4c3e-8264-a40d63fd6883",
        "frustrated": "1f017bcb-02e5-460d-989b-db065c0c6122",
        "sad": "530e2e20-58e2-45d8-b0a5-4594f4915944",
    },
    "oliver": {
        "neutral": "e3596645-b1af-469e-b857-f18ddedc7652",
    },
    "jane": {
        "sarcasm": "a3e41ea8-020b-44c0-8d8b-f6cc03524e31",
    }
}

async def mistral_chat(text: str, system_prompt: Optional[str] = None) -> str:
    """Send chat to Mistral Large."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": text})

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{MISTRAL_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "mistral-large-latest",
                "messages": messages,
                "max_tokens": 500,
            },
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

async def mistral_tts(text: str, voice_id: str) -> bytes:
    """Generate speech using Mistral Voxtral TTS."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{MISTRAL_BASE_URL}/audio/speech",
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "voxtral-mini-tts-latest",
                "input": text,
                "voice_id": voice_id,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            if "audio_data" in data:
                return base64.b64decode(data["audio_data"])
            return resp.content
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

async def edge_tts(text: str, voice: str = "th-TH-PremwadeeNeural") -> bytes:
    """Generate Thai speech using edge-tts."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    result = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            result += chunk["data"]
    return result

# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/process")
async def voice_process(req: VoiceProcessRequest):
    """
    Process voice command text via Gemini.
    Extracts menu items (+ optional table number) and returns structured result.
    """
    from ai_service import get_ai_service

    system = (
        "คุณคือผู้ช่วยสั่งอาหารของระบบ POS ร้านอาหารไทย\n"
        "\n"
        "ภารกิจ: วิเคราะห์ข้อความที่ลูกค้าพูดหรือพิมพ์ แลวแยกรายการอาหารและโต๊ะ\n"
        "\n"
        "เมนูที่มี:\n"
        "- Appetizer: Spring Rolls, Tom Yum Soup, Som Tum Thai, Satay Chicken, Fish Cakes, "
        "Tod Mun Goong, Larb Gai, Miang Kham\n"
        "- Main Course: Pad Thai Goong, Green Curry Chicken, Massaman Curry, "
        "Pad Kra Pao Moo, Tom Kha Gai, Pad See Ew, Khao Soi, Panang Curry, "
        "Fried Rice Seafood, Stir-fried Basil Seafood, Grilled Pork Neck, Steamed Fish with Lime\n"
        "- Dessert: Mango Sticky Rice, Thai Roti, Ice Cream (Coconut), Khao Tom Mud, "
        "Lod Chong, Bua Loy\n"
        "- Beverage: Thai Iced Tea, Thai Iced Coffee, Coconut Water, Lemonade, Soda, Water, "
        "Singha Beer, Chang Beer, Smoothie (Fruit)\n"
        "- Side Dish: Steamed Rice, Sticky Rice, Fried Egg, Extra Veggies\n"
        "\n"
        "ถ้าลูกค้าบอกเลขโต๊ะ เชน 'โต๊ะ 3' หรือ 'table 5' ใหใส่ table_id ด้วย\n"
        "ถ้าไม่บอกเลขโต๊ะ ใหใช้ \"takeaway\"\n"
        "\n"
        "ตอบกลับในรูปแบบ JSON เท่านั้น หามมีข้อความอื่น:\n"
        "{\"action\": \"identify\", \"items\": [{\"name\": \"Pad Thai Goong\", \"quantity\": 2}], \"table_id\": \"T03\"}\n"
        "\n"
        "หรือถ้าเป็นคำถามทั่วไป: {\"action\": \"question\", \"reply\": \"ข้อความตอบกลับ\"}\n"
        "\n"
        "Mapping โต๊ะ: โต๊ะ 1=T01, โต๊ะ 2=T02, ... โต๊ะ 20=T20, takeaway=takeaway"
    )

    try:
        svc = get_ai_service()
        session_id = req.session_id or f"voice-{datetime.now().timestamp()}"
        
        # If frontend sends conversationHistory, seed the backend session with it
        if req.conversationHistory:
            history = svc.get_or_create_conversation(session_id)
            if not history:  # Only seed if empty
                for msg in req.conversationHistory:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "model":
                        history.append({"role": "model", "parts": [content]})
                    else:
                        history.append({"role": "user", "parts": [content]})
        
        reply = svc.chat(session_id, req.text, context=system)

        # Try to parse JSON from reply (handle nested braces and markdown code fences)
        import re
        # Strip code fences first
        cleaned = re.sub(r'```(?:json)?\s*', '', reply).strip()
        # Find outermost JSON object
        brace_depth = 0
        json_start = -1
        for i, c in enumerate(cleaned):
            if c == '{':
                if brace_depth == 0:
                    json_start = i
                brace_depth += 1
            elif c == '}':
                brace_depth -= 1
                if brace_depth == 0 and json_start >= 0:
                    json_str = cleaned[json_start:i+1]
                    try:
                        result = json.loads(json_str)
                        items = result.get("items", [])
                        table_id = result.get("table_id", "takeaway")
                        action = result.get("action", "question")
                        return {
                            "success": True,
                            "action": action,
                            "items": items,
                            "table_id": table_id,
                            "reply": result.get("reply", reply)
                        }
                    except json.JSONDecodeError:
                        pass
                    break

        return {"success": True, "action": "question", "items": [], "table_id": "takeaway", "reply": reply}
    except Exception as e:
        logger.error("Voice process error: %s", e)
        return {"success": False, "action": "error", "items": [], "table_id": "takeaway", "reply": str(e)}


@router.get("/voices")
async def list_voices():
    """List all available TTS voices."""
    return {
        "mistral": PRESET_VOICES,
        "edge_tts": [
            "th-TH-Premwadee (Thai female)",
            "th-TH-Niwat (Thai male)",
            "en-US-JennyNeural",
            "en-US-GuyNeural",
        ]
    }

@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Transcribe audio file to text (supports webm/mp3/wav via ffmpeg conversion)."""
    import subprocess
    import speech_recognition as sr
    recognizer = sr.Recognizer()
    
    audio_bytes = await file.read()
    
    # Save uploaded file (could be .webm from MediaRecorder)
    orig_ext = os.path.splitext(file.filename or "audio.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=orig_ext, delete=False) as tmp:
        tmp.write(audio_bytes)
        raw_path = tmp.name
    
    wav_path = raw_path + ".wav"
    try:
        # Convert to WAV with ffmpeg (handles webm/opus → wav)
        subprocess.run(
            ["ffmpeg", "-y", "-i", raw_path, "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True, timeout=30
        )
        
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)
        
        text = recognizer.recognize_google(audio, language="th-TH")
        return TranscribeResponse(text=text, language="th")
    except sr.UnknownValueError:
        return TranscribeResponse(text="", language="th")
    except sr.RequestError as e:
        logger.error("STT API error: %s", e)
        raise HTTPException(status_code=503, detail=f"STT service error: {e}")
    finally:
        for p in [raw_path, wav_path]:
            if os.path.exists(p):
                os.unlink(p)

@router.post("/chat", response_model=ChatResponse)
async def voice_chat(req: ChatRequest):
    """Process voice command text through Mistral Large."""
    system = req.system_prompt or (
        "You are a voice assistant for Super Appsheet POS system. "
        "Keep responses short and conversational. Respond in the same language "
        "as the user's input."
    )
    
    response_text = await mistral_chat(req.text, system)
    
    # Try to generate TTS audio
    audio_b64 = None
    try:
        voice_id = PRESET_VOICES.get("paul", {}).get("confident")
        if voice_id:
            audio_data = await mistral_tts(response_text, voice_id)
            audio_b64 = base64.b64encode(audio_data).decode()
    except Exception as e:
        logger.warning("TTS generation failed (non-critical): %s", e)
    
    return ChatResponse(
        text=response_text,
        audio_url=f"data:audio/mp3;base64,{audio_b64}" if audio_b64 else None,
    )

@router.post("/synthesize")
async def synthesize(req: TTSRequest):
    """Convert text to speech."""
    voice_map = PRESET_VOICES.get(req.voice, {}).get(req.mood) or \
                PRESET_VOICES.get("paul", {}).get("confident")
    
    if voice_map:
        # Use Mistral TTS
        audio_data = await mistral_tts(req.text, voice_map)
        return Response(
            content=base64.b64decode(
                json.loads(audio_data)["audio_data"]
                if isinstance(audio_data, bytes) and b"audio_data" in audio_data[:100]
                else audio_data.decode() if isinstance(audio_data, bytes)
                else audio_data
            ),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"}
        )
    else:
        # Fallback to edge-tts
        audio_data = await edge_tts(req.text)
        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"}
        )
