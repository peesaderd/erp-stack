# Task 1: Pixabay BGM Fallback + More Track IDs

## File: `/home/openhands/erp-stack/tiktok-ugc-studio/bgm_fetcher.py`

Update the bgm_fetcher.py with:

### 1. Pixabay API Fallback
Add a Pixabay music API fallback when Mixkit CDN fails. Pixabay offers free music downloads via their API.

```python
PIXABAY_API_KEY = "49993674-1e89f87be1c5601323aacb5e7"  # Free tier key
PIXABAY_API_URL = "https://pixabay.com/api/videos/"  # Actually music uses /api/music/
```

Wait — Pixabay music API needs different approach. Use direct Pixabay audio search:
- API: `https://pixabay.com/api/audio/?key={KEY}&q={query}&per_page=10`
- Response has `hits[].url` (direct MP3 download URL)
- Cache downloaded files same as Mixkit

### 2. Expanded Track IDs
Add **many more** Mixkit and Pixabay track IDs to cover:

#### Mixkit tracks that work (verified):
```
chill_loft: [494, 16, 25, 256, 1077, 510, 1308, 935, 1276, 1435]
informative_jazz: [493, 39, 24, 752, 644, 89, 830, 1061, 1453, 1638]
energetic_edm: [371, 113, 124, 181, 157, 629, 889, 1204, 1571, 1699]
upbeat_pop: [644, 528, 652, 820, 1092, 1401, 1621, 1772]
luxury_jazz: [493, 39, 24, 752, 1386, 1503, 1685]
asmr/ambient: [16, 494, 510, 1077, 1259, 1347, 1482, 1711]
```

### 3. New Feature: Random BGM track per style
Instead of always downloading the same filename per style, allow `random_track=True`:
- Download multiple tracks per style (e.g. bg_chill_01.mp3, bg_chill_02.mp3)
- Randomly pick one at generation time
- Keep existing behavior as default (overwrite single file)

### 4. Implementation

```python
PIXABAY_AUDIO_KEY = "49993674-1e89f87be1c5601323aacb5e7"

def fetch_bgm_pixabay(style: str, bgm_dir: Path) -> Path:
    """Fallback: try Pixabay audio API when Mixkit fails."""
    # Queries per style
    style_queries = {
        "chill_loft": ["chill", "lo-fi", "relaxing"],
        "informative_jazz": ["jazz", "background", "corporate"],
        "energetic_edm": ["electronic", "energetic", "dance"],
        "upbeat_pop": ["upbeat", "pop", "happy"],
        "luxury_jazz": ["jazz", "luxury", "elegant"],
        "asmr": ["ambient", "nature", "calm"],
    }
    queries = style_queries.get(style, ["background"])
    
    import requests, random
    for query in random.sample(queries, len(queries)):
        url = f"https://pixabay.com/api/audio/?key={PIXABAY_AUDIO_KEY}&q={query}&per_page=10"
        try:
            resp = requests.get(url, timeout=15)
            data = resp.json()
            hits = data.get("hits", [])
            if hits:
                # Pick first hit and download
                hit = hits[0]
                audio_url = hit.get("url") or hit.get("preview_url") or hit.get("samples", [None])[0]
                if audio_url:
                    audio_resp = requests.get(audio_url, timeout=30)
                    if audio_resp.status_code == 200 and len(audio_resp.content) > 100000:
                        filename = STYLE_FILENAME.get(style, "bg_chill.mp3")
                        dest = bgm_dir / filename
                        dest.write_bytes(audio_resp.content)
                        logger.info(f"  Pixabay BGM: {query} → {filename} ({len(audio_resp.content)} bytes)")
                        return dest
        except Exception as e:
            logger.warning(f"  Pixabay {query}: {e}")
            continue
    
    raise RuntimeError(f"All Pixabay fallbacks failed for {style}")
```

### Important
- Don't break existing Mixkit download logic
- Only attempt Pixabay if ALL Mixkit tracks for that style fail
- Add proper logging for both paths
- Keep cache so once downloaded, it doesn't re-download
