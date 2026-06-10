# 🛒 Product Scraper — Blueprint & Project Perspective

## 🎯 Objective
สร้างระบบ Scrape สินค้าจาก E-commerce ไทย (TikTok Shop, Shopee, Lazada, Facebook) 
เพื่อป้อนข้อมูลเข้า AI Pipeline สร้างคลิป Affiliate อัตโนมัติ

**Target Platforms (Thailand Main Stream):**
1. **TikTok Shop** 🏆 — อันดับ 1 E-commerce ไทย
2. **Shopee** 🥈 — Marketplace ใหญ่สุด
3. **Lazada** 🥉 — รองจาก Shopee
4. **Facebook Marketplace / Groups** — ขายของในกลุ่ม

---

## 🏗 สถาปัตยกรรม

```
User ส่ง Product URL
     │
     ▼
┌─────────────────────────────────────┐
│         Product Scraper API          │  ← Service ที่ :8106
│  http://localhost:8106               │
│                                     │
│  Residential Proxy → Scrape → Parse │
└──────────────────┬──────────────────┘
                   │
                   ▼
        Product Data (JSON)
┌─────────────────────────────────────┐
│  name        — "เซรั่มบำรุงผิว"       │
│  price       — ฿399                  │
│  brand       — "SKINTIFIC"           │
│  images[]    — [url1, url2, ...]     │
│  rating      — 4.8 ★ (2.5K reviews)  │
│  description — ข้อความสินค้า          │
│  features[]  — ["ไฮยาลูรอน", ...]    │
│  reviews[]   — รีวิวลูกค้าจริง        │
│  category    — "Skincare"            │
│  source_url  — URL ต้นทาง            │
│  source_site — "tiktok" / "shopee"   │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│         AI Pipeline (TUS)            │
│                                     │
│  Product Data → Script Gen          │
│  Image → Seedream/Flux (optional)   │
│  Script → MiniMax Voice             │
│  Prompt → WaveSpeed Video            │
│  → FFmpeg Merge → Final Clip        │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│      Post For Me — Social Auto Post │
│                                     │
│  TikTok Shop / Facebook / IG / YT   │
└─────────────────────────────────────┘
```

---

## 📂 File Structure (วางใน modules/product/)

```
modules/product/
├── __init__.py
├── README.md              ← เอกสารนี้
├── scraper.py             ← Main Scraper Engine
├── platforms/
│   ├── __init__.py
│   ├── base.py            ← Base Scraper class
│   ├── tiktok_shop.py     ← TikTok Shop Scraper
│   ├── shopee.py          ← Shopee Scraper
│   ├── lazada.py          ← Lazada Scraper
│   └── facebook.py        ← Facebook Marketplace/Group Scraper
├── proxy.py               ← Residential Proxy Manager (rotate IP)
├── parser.py              ← Data parser (Normalize fields)
├── server.py              ← FastAPI server (port 8106)
├── requirements.txt       ← dependencies
├── tests/
│   ├── test_tiktok.py
│   ├── test_shopee.py
│   ├── test_lazada.py
│   └── test_facebook.py
└── sessions/              ← Session cookies (gitignored)
```

---

## 🔧 Technical Approach

### 1. Residential Proxy
```
Provider: (ระบุชื่อ)
IP Rotation: แต่ละ request → random IP
Rate Limit: ~5-10 req/min ต่อ IP
```

### 2. กลยุทธ์ Scrape ต่อ Platform

| Platform | วิธี | ยาก |
|----------|------|-----|
| **TikTok Shop** | TikTok API (session cookie) + Playwright fallback | ⚠️ ปานกลาง |
| **Shopee** | Desktop web scrape + API endpoint mimic | 🔥 ยาก (bot detection แรง) |
| **Lazada** | Desktop web scrape + Playwright | ⚠️ ปานกลาง |
| **Facebook** | Graph API + Playwright login | 🔥 ยาก (ต้อง login) |

### 3. Fallback Strategy
```
1. Try Direct API (ถ้ามี) → Fastest
2. Try Playwright headless → Medium
3. Try Playwright + Residential Proxy → Slow but reliable
4. Manual fallback → Return partial data
```

### 4. Data Schema (Output)

```python
{
    "success": True,
    "method": "api|playwright|cache",
    "source_site": "tiktok|shopee|lazada|facebook",
    "product": {
        "name": str,
        "price": float | None,
        "currency": "THB",
        "brand": str | "",
        "images": [str],          # URLs
        "video_url": str | "",     # ถ้ามีคลิปสินค้า
        "rating": float | None,   # 1-5
        "review_count": int | 0,
        "description": str,
        "features": [str],        # จุดเด่น
        "reviews": [              # Top reviews
            {"text": str, "rating": int}
        ],
        "category": str,
        "tags": [str],
        "seller_name": str,
        "seller_url": str,
    },
    "scraped_at": "2026-06-10T13:00:00Z",
    "cached": False,
    "proxy_used": "xxx.xxx.xxx.xxx"
}
```

---

## 🔗 Integration กับ TUS

### Endpoint ที่มีแล้ว (ใน main.py :8105)

```
POST /product/scrape-and-generate
```
- รับ `url` + `use_vision` (optional)
- เรียก Product Scraper :8106
- ได้ Product Data → สร้าง Script → return

### Endpoint ที่ต้องเพิ่ม

```
GET  /product/status            → ระบบ Scraper status
POST /product/scrape-only       → Scrape อย่างเดียว ไม่สร้าง script
POST /product/scrape-batch      → Scrape หลาย URL พร้อมกัน
```

---

## 🗺 Roadmap

### Phase 1 — TikTok Shop ✅ (low hanging fruit)
- [ ] TikTok Shop Scraper (ใช้ API mimic + session)
- [ ] รองรับ URL: `tiktok.com/@shop/...`

### Phase 2 — Shopee 🔥 (hardest)
- [ ] Shopee Desktop Scraper (Playwright + Proxy)
- [ ] Anti-bot Detection (headers, timing, mouse movement)
- [ ] รองรับ URL: `shopee.co.th/...`

### Phase 3 — Lazada
- [ ] Lazada Scraper
- [ ] รองรับ URL: `lazada.co.th/...`

### Phase 4 — Facebook
- [ ] Facebook Marketplace Scraper (must login)
- [ ] Facebook Group Scraper
- [ ] รองรับ URL: `facebook.com/marketplace/...`

### Phase 5 — Optimization
- [ ] Caching (Redis/disk)
- [ ] Rate Limiter
- [ ] Proxy Rotation auto
- [ ] Error tracking + retry

---

## 💰 Cost Estimation

| Component | Cost |
|-----------|------|
| Residential Proxy | ~$20-50/เดือน (ตาม provider) |
| Server (มีแล้ว) | $0 (VPS ปัจจุบัน) |
| Playwright Browser | $0 |
| Maintenance | ~2h/สัปดาห์ |

**เทียบกับการ scrap เองกับใช้ API สําเร็จรูป**
| วิธี | Cost/เดือน | Scalability |
|-----|-----------|-------------|
| ทำเอง (Playwright + Proxy) | ~$20-50 | จำกัดตาม proxy pool |
| ScrapingBee/ScraperAPI | $49-99 | Scale ได้จำกัด |
| Residential Proxy + ทำเอง ✅ | $20-50 ✅ | ควบคุมได้ 100% |

---

## 🔐 Environment Variables ที่ต้องมี

```bash
# Proxy
export PROXY_URL="http://user:pass@residential-proxy:port"
export PROXY_POOL_SIZE=10

# Platform Sessions (เก็บ cookies)
export TIKTOK_SESSION_COOKIE="..."
export SHOPEE_SESSION_COOKIE="..."
export LAZADA_SESSION_COOKIE="..."
export FACEBOOK_SESSION_COOKIE="..."

# TUS Connection
export SCRAPER_API_URL="http://localhost:8106"
```

---

## 📝 Notes สำหรับ Developer

1. **แต่ละ platform มีโครงสร้าง HTML ที่เปลี่ยนตลอด** — ใช้ CSS selectors ที่ stable (data-attr > class name)
2. **ถ้า scrape ได้ข้อมูลไม่ครบ** — return partial data, อย่า throw error
3. **การเรียก proxy แต่ละครั้ง → random IP** — ไม่ให้ platform detect
4. **Cache ผล scrape ไว้ 1 ชม.** — ลดรอบเรียก proxy
5. **TikTok Shop API session หมดอายุ 24 ชม.** — ต้อง refresh
6. **Shopee detect bot แรงที่สุด** — ต้องใช้ Playwright + emulate human behavior
7. **ทุก platform ต้องรองรับ fallback** — API fail → Playwright → Manual

---

## ❓ FAQ

### Q: ทำไมไม่ใช้ Scraper สำเร็จรูป?
> เพราะเราต้องการ control 100% + ใช้ residential proxy ของเราเอง + รองรับ platform ไทยโดยเฉพาะ (ที่มี structure ต่างจากของ global)

### Q: Shopee detect bot แรงขนาดไหน?
> แรงมาก — ใช้ fingerprinting + mouse movement analysis + timing analysis → ต้องใช้ Playwright full emulation

### Q: จำเป็นต้องมี session cookie ไหม?
> สำหรับ TikTok Shop (API) และ Facebook (ต้อง login) — จำเป็น สำหรับ Shopee/Lazada web scrape ไม่ต้อง login แต่ proxy ต้อง clean
