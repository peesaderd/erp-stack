"""Gemini 3.1 Flash TTS Preview — unified TTS for all pipelines."""
import os, json, base64, requests, tempfile
from typing import Optional

MODEL = "gemini-3.1-flash-tts-preview"
VOICE = "Aoede"

def gemini_text_to_speech(text, output_path=None, voice=VOICE):
    api_key = os.environ.get("GEMINI_API_KEY") or ""
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (MODEL, api_key)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}
        }
    }
    resp = requests.post(url, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError("Gemini TTS error %s: %s" % (resp.status_code, resp.text[:300]))
    data = resp.json()
    for p in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if "inlineData" in p:
            b64 = p["inlineData"]["data"]
            audio = base64.b64decode(b64)
            if output_path is None:
                fd, output_path = tempfile.mkstemp(suffix=".mp3")
                os.close(fd)
            with open(output_path, "wb") as f:
                f.write(audio)
            print("[GeminiTTS] %d bytes -> %s" % (len(audio), output_path))
            return output_path
    raise RuntimeError("No audio data in Gemini TTS response")

if __name__ == "__main__":
    test = gemini_text_to_speech("สวัสดีครับ ทดสอบระบบเสียง", "/tmp/gemini_tts_test.mp3")
    print("Test saved:", test)
