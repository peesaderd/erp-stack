import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = [
    "https://kidobits.m2igen.com/kidobits/v2/audio/teach_blend_how.mp3",
    "https://kidobits.m2igen.com/kidobits/v2/audio/teach_intro_l201.mp3",
    "https://kidobits.m2igen.com/kidobits/v2/audio/word_at.mp3",
    "https://kidobits.m2igen.com/kidobits/v2/audio/sp_a.mp3",
    "https://kidobits.m2igen.com/kidobits/v2/audio/ph_a.mp3",
    "https://kidobits.m2igen.com/kidobits/v2/audio/praise_great.mp3",
]

req_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

for u in urls:
    try:
        req = urllib.request.Request(u, headers=req_headers)
        with urllib.request.urlopen(req, context=ctx, timeout=5) as res:
            print(f"{res.status} OK: {u} (size={len(res.read())})")
    except Exception as e:
        print(f"FAILED: {u} -> {e}")
