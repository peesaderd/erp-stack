"""Backfill gender for TUS products using Mistral Vision.

Reads products with empty gender from tus_products.db, sends the product image
+ title + description to Mistral, and classifies gender as female/male.
Includes retry with exponential backoff for rate limits (429).
"""
import os, json, sqlite3, base64, sys, time, logging
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('backfill_gender')

TUS_DB = '/home/openhands/erp-stack/tiktok-ugc-studio/tus_products.db'
IMAGE_DIR = '/home/openhands/erp-stack/tiktok-ugc-studio/storage/product_images'
MISTRAL_KEY = os.environ.get('MISTRAL_API_KEY', '')
MISTRAL_URL = 'https://api.mistral.ai/v1/chat/completions'
MISTRAL_MODEL = 'mistral-large-latest'
MAX_RETRIES = 5
BASE_DELAY = 10.0

PROMPT = '''Analyze this product image and its details for a TikTok UGC video.
Determine the target gender of the product. Return ONLY valid JSON:
{"gender": "female" or "male", "reason": "short reason"}

Rules:
- gender MUST be exactly "female" or "male" (no other values).
- Look at the product image carefully (colors, design, style, packaging).
- Consider the title and description.
- If the product is clearly for women (dress, skirt, makeup, skincare, women's fashion) -> female
- If clearly for men (men's shirt, suit, tie, men's grooming) -> male
- For unisex/neutral products, choose the gender that is MOST LIKELY the primary target audience for the video.
- NEVER return empty string or "unisex". Always pick female or male.
'''

def load_image_base64(path):
    try:
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        logger.warning('Cannot read image %s: %s', path, e)
        return None

def classify_gender(product_id, title, description, image_path):
    img_b64 = load_image_base64(image_path)
    if not img_b64:
        return None, 'no image'
    content = [
        {'type': 'text', 'text': PROMPT + '\nTitle: ' + title + '\nDescription: ' + (description or 'N/A')},
        {'type': 'image_url', 'image_url': 'data:image/jpeg;base64,' + img_b64},
    ]
    payload = {
        'model': MISTRAL_MODEL,
        'messages': [{'role': 'user', 'content': content}],
        'temperature': 0.1,
        'max_tokens': 200,
    }
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(MISTRAL_URL, headers={
                    'Authorization': 'Bearer ' + MISTRAL_KEY,
                    'Content-Type': 'application/json',
                }, json=payload)
                if resp.status_code == 429:
                    wait = BASE_DELAY * (2 ** attempt)
                    logger.warning('Rate limited (429), retry %d/%d in %.0fs', attempt+1, MAX_RETRIES, wait)
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    logger.error('Mistral error %s: %s', resp.status_code, resp.text[:200])
                    return None, 'api_error_' + str(resp.status_code)
                text = resp.json()['choices'][0]['message']['content']
                start = text.find('{')
                end = text.rfind('}')
                if start >= 0 and end > start:
                    data = json.loads(text[start:end+1])
                    g = str(data.get('gender', '')).strip().lower()
                    if g in ('female', 'f', 'women', 'woman'):
                        return 'female', data.get('reason', '')
                    if g in ('male', 'm', 'men', 'man'):
                        return 'male', data.get('reason', '')
                return None, 'bad_response: ' + text[:100]
        except Exception as e:
            logger.error('Mistral exception: %s', e)
            wait = BASE_DELAY * (2 ** attempt)
            time.sleep(wait)
    return None, 'max_retries_exceeded'

def main():
    if not MISTRAL_KEY:
        logger.error('MISTRAL_API_KEY not set')
        sys.exit(1)
    conn = sqlite3.connect(TUS_DB)
    rows = conn.execute("SELECT product_id, title, description, images FROM tus_products WHERE gender='' OR gender IS NULL").fetchall()
    logger.info('Found %d products with empty gender', len(rows))
    updated = 0
    failed = 0
    for product_id, title, description, images_json in rows:
        image_path = None
        try:
            imgs = json.loads(images_json) if images_json else []
            if imgs:
                first = imgs[0]
                fname = os.path.basename(first)
                image_path = os.path.join(IMAGE_DIR, fname)
        except Exception:
            pass
        if not image_path or not os.path.exists(image_path):
            logger.warning('No image for %s, skipping', product_id)
            failed += 1
            continue
        gender, reason = classify_gender(product_id, title, description, image_path)
        if gender:
            conn.execute('UPDATE tus_products SET gender=? WHERE product_id=?', (gender, product_id))
            conn.commit()
            updated += 1
            logger.info('%s: %s (%s)', product_id, gender, reason)
        else:
            failed += 1
            logger.warning('%s: FAILED (%s)', product_id, reason)
        time.sleep(8.0)
    conn.close()
    logger.info('DONE: updated=%d, failed=%d', updated, failed)

if __name__ == '__main__':
    main()
