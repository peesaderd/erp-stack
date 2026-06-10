# 🧠 Product Intelligence Hub — Blueprint & Project Perspective

## 1. Vision
เปลี่ยนจาก "Product Scraper" → **Product Intelligence Hub (PIH)**
เป็นศูนย์กลางข้อมูลสินค้าอัจฉริยะ ที่รวบรวม วิเคราะห์ และแจกจ่ายข้อมูลสินค้าจากทุก E-commerce Platform ในไทย

> "Google Analytics สำหรับ Product Intelligence"

---

## 2. สถาปัตยกรรม (Module-Based)

```
                        Product Intelligence Hub
                               :8106
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   │  Data Layer  │    │  Intel Layer │    │  Output Layer│
   │  (Scrape)    │    │  (Analyze)   │    │  (Serve)     │
   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
          │                   │                   │
          ▼                   ▼                   ▼
   ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
   │ TikTok Shop  │    │ AI Analyzer  │    │ TUS (Internal)   │
   │ Shopee       │    │  วิเคราะห์    │    │ Affiliate Dash   │
   │ Lazada       │───▶│  รีวิว/ราคา   │───▶│ Client API (ขาย)  │
   │ Facebook     │    │  หมวดหมู่    │    │ Mobile App API   │
   │ Central      │    │  จุดเด่น     │    │ Webhook          │
   └──────────────┘    └──────────────┘    └──────────────────┘
```

---

## 3. Pricing & Subscription Model

### 3.1 สำหรับ TUS (TikTok UGC Studio)

| TUS Tier | Product Scrape | Cross Platform | AI Analysis | API Access |
|----------|---------------|----------------|-------------|------------|
| **Pay-as-you-go** | ✅ 1 platform เท่านั้น | ❌ | ❌ | ❌ |
| **Subscription** | ✅ Unlimited | ✅ ครบทุกแพลตฟอร์ม | ✅ Autoวิเคราะห์ | ✅ |

**Logic:** Subscription = ใช้ Feature เต็ม → ยิ่งใช้ product scrape เร็ว → ยิ่งหมด quota เร็ว → ยิ่งต้องอัพเกรดเร็ว → เราขาย subscription ได้มากขึ้น 🚀

### 3.2 Client API (ขายให้ Third Party)  ⚠️

#### ⚠️ ความเสี่ยง — Conflict กับ Partner/Platform

การขาย Scraped Data API ให้ Third Party มีความเสี่ยง:

| ความเสี่ยง | ระดับ | ผลกระทบ |
|-----------|-------|----------|
| Platform (Shopee/Lazada/TikTok) detect → Block IP | 🔴 สูง | Scraper ใช้ไม่ได้ทั้งระบบ |
| ผิด TOS (Terms of Service) ของ Platform | 🔴 สูง | โดนฟ้อง/บล็อค |
| ข้อมูลรั่ว → ขโมย IP ทรัพย์สินทางปัญญา | 🟡 กลาง | โดนฟ้อง |
| Competitor เอา Data ไปสร้างธุรกิจแข่ง | 🟡 กลาง | เสียลูกค้า |

#### ✅ ทางรอด: ต่อยอด API ไม่ขาย Data ดิบ

**ห้ามขาย Data API ตรงๆ** — ให้ Third Party เรียก API ที่มี Value Chain ต่อเนื่อง:

| รูปแบบ | ปลอดภัย? | คำอธิบาย |
|--------|---------|----------|
| ❌ ขาย Scraped Data API | 🔴 เสี่ยง | "ขอมูลราคาสินค้าทั้งหมดใน Shopee" |
| ✅ **ขาย Content Creation API** | 🟢 ปลอดภัย | "ส่ง URL สินค้า → ได้คลิป Affiliate พร้อมโพสต์" |
| ✅ **ขาย Price Alert API** | 🟢 ปลอดภัย | "แจ้งเตือนเมื่อสินค้าลดราคา" |
| ✅ **ขาย Affiliate Matching API** | 🟢 ปลอดภัย | "ส่งสินค้า → ได้ลิงก์ Affiliate + เนื้อหา" |
| ✅ **ขาย UGC Generation API** | 🟢 ปลอดภัย | "ส่ง URL → ได้คลิป AI พร้อมโพสต์ทุก platform" |

**กฏเหล็ก: Third Party ได้ OUTPUT ของเรา (Content), ไม่ใช่ RAW DATA**

#### ✅ ระบบคล้ายที่คุณว่า — "สร้างระบบอีกอันดึง API ไป"

แนวทางที่ปลอดภัย — **Agent/Middleware Layer**:

```
Client App (Third Party)
     │
     ▼
┌─────────────────────┐
│   Agent API Layer    │  ← API ที่เปิดให้ Third Party (จ่ายตัง)
│   (New Service)      │
│   :8123              │
│                      │
│  - Rate Limit        │
│  - Billing           │
│  - Logging           │
│  - Obfuscate Source  │  ← ซ่อน source platform
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Product Intel Hub  │  ← Internal เท่านั้น
│   :8106              │
└─────────────────────┘
```

**ด้วย System แบบนี้:**
- Third Party ไม่รู้ว่าเราดึงข้อมูลจากไหน
- Third Party ไม่สามารถ replicate data ของเรา
- Third Party ซื้อ **Content/Service** ไม่ใช่ Data
- ถ้า Platform หรือ Partner ตรวจสอบ — เราแค่บอกว่า "เราให้บริการ Content Creation API, ไม่มี Data API"

---

## 4. Feature Matrix

### Data Layer (Scrape)
| Feature | Free Tier | Subscription |
|---------|-----------|--------------|
| Scrape Shopee | ✅ | ✅ |
| Scrape Lazada | ❌ | ✅ |
| Scrape TikTok Shop | ❌ | ✅ |
| Scrape Facebook | ❌ | ✅ |
| Scrape All Platforms | ❌ | ✅ |
| Cross-platform Same Product | ❌ | ✅ |
| Cache Results (1hr) | ✅ | ✅ |
| Fresh Results (no cache) | ❌ | ✅ |

### Intel Layer (Analyze)
| Feature | Free Tier | Subscription |
|---------|-----------|--------------|
| Product Name Extraction | ✅ | ✅ |
| Price Extraction | ✅ | ✅ |
| Image Extraction | ✅ | ✅ |
| AI Review Summary | ❌ | ✅ |
| Price Trend Analysis | ❌ | ✅ |
| Competitor Matching | ❌ | ✅ |
| Affiliate Link Auto-Gen | ❌ | ✅ |
| Script Content Auto-Gen | ❌ | ✅ |

### Output Layer (Serve)
| Feature | Free | Sub | Client API |
|---------|------|-----|------------|
| TUS Pipeline Integration | ✅ | ✅ | ❌ |
| Affiliate Dashboard | ❌ | ✅ | ❌ |
| Price Monitor/Alert | ❌ | ✅ | ❌ |
| Third Party API | ❌ | ❌ | ✅ (ผ่าน Agent Layer) |

---

## 5. file Structure

```
modules/product/
├── PRODUCT_INTELLIGENCE_HUB.md   ← เอกสารนี้ (Blueprint)
├── main.py                       ← FastAPI server :8106
├── scraper.py                    ← Main Scraper Engine
├── analyzer.py                   ← AI Analysis
├── export_service.py             ← Export API ให้ Client
├── scheduler.py                  ← Cron job ตามราคา
├── db_models.py                  ← Database Schema
├── simple_proxy.py               ← Proxy Rotator
├── platforms/
│   ├── base.py                   ← Base Scraper class
│   ├── tiktok_shop.py            ← TikTok Shop
│   ├── shopee.py                 ← Shopee
│   ├── lazada.py                 ← Lazada
│   └── facebook.py               ← Facebook
├── agent_api/                    ← Agent Layer สำหรับ Third Party
│   ├── __init__.py
│   ├── server.py                 ← :8123
│   ├── billing.py
│   └── routes.py
└── ui/                           ← Dashboard
```

---

## 6. Business Model — Subscription Tiers

| Tier | Price/เดือน | Scrapes/วัน | Platforms | AI Analysis | Client API |
|------|------------|------------|-----------|-------------|------------|
| **Free** | $0 | 10 | 1 platform | ❌ | ❌ |
| **Starter** | $9 | 100 | 2 platforms | ❌ | ❌ |
| **Pro** | $29 | 500 | All | ✅ | ❌ |
| **Business** | $99 | 2,000 | All + Cross | ✅ | ✅ (ผ่าน Agent) |
| **Enterprise** | Custom | Unlimited | All + Custom | ✅ + Custom Agent | ✅ |

**PS. พวกที่ทำ Affiliate แบบเรา → ใช้ Subscription TUS ที่รวม Feature นี้อยู่แล้ว**

---

## 7. เปรียบเทียบ: Scraper vs Intelligence Hub

| มิติ | Product Scraper ธรรมดา | **Product Intelligence Hub** ✅ |
|------|----------------------|--------------------------------|
| Function | แค่ดึงข้อมูลมาให้ | รวบรวม + วิเคราะห์ + แจกจ่าย + เสนอลูกค้า |
| Business Model | ไม่มี (เป็น tool) | มี subscription tiers + client API |
| Security | เปิด API ตรง | มี Agent Layer ป้องกัน |
| การใช้งาน TUS | ดึงมาใช้เฉยๆ | **Feature Premium ที่ขาย Subscription ต่อได้** |
| Scability | Scrape เดียว | Multi-platform + Cross-platform |
| AI | ❌ | ✅ (วิเคราะห์รีวิว, สร้าง content อัตโนมัติ) |

---

## 8. Roadmap

| Phase | Feature | Timeline |
|-------|---------|----------|
| **P1** | TikTok Shop Scraper | สัปดาห์นี้ |
| **P2** | Shopee Scraper + Proxy Rotator | สัปดาห์หน้า |
| **P3** | Lazada Scraper + AI Analyzer | สัปดาห์ถัดไป |
| **P4** | Subscription Tiers + TUS Integration | |
| **P5** | Agent API Layer (สำหรับ Third Party) | |
| **P6** | Facebook Scraper + Mobile App | |
| **P7** | Price Monitor + Alert System | |

---

## 9. Environment Variables (New)

```bash
# Subscription/API Keys
export SCRAPER_SUB_KEY="..."
export SCRAPER_AGENT_KEY="..."

# Proxy
export PROXY_URL="http://user:pass@proxy:port"
export PROXY_POOL_SIZE=10

# Database
export DATABASE_URL="sqlite:///modules/product/scraper.db"
export REDIS_URL="redis://localhost:6379"

# Agent API Layer (ขาย API)
export AGENT_API_URL="http://localhost:8123"
export AGENT_API_KEY="..."
```

---

## 10. หลักการสำคัญสำหรับ Developer

1. **อย่าขาย Raw Data API** — ขาย Content/Service ที่ผ่าน Process ของเราแล้ว
2. **Agent Layer ป้องกันข้อมูล** — Third Party ไม่รู้ source platform
3. **Subscription = Premium** — Pay-as-you-go = พื้นฐานเท่านั้น
4. **ทุก Feature ต้องมี TUS Integration** — TUS คือ Flagship Client
5. **Logging ทุก request** — รู้ว่าใครเรียกอะไร ตอนไหน
6. **Rate Limit ทุกเลเยอร์** — ทั้ง scraper → DB → API
