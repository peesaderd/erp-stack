# TikTok UGC Studio

## 🎯 Vision
AI-driven UGC (User Generated Content) video creation platform for TikTok, built on AiBot Auto-Gen v4.5 prompt system. Generate realistic product review videos with consistent characters, natural dialogue, and professional quality — all via API.

## 🚀 Core Features
- **AI Script Generation** — TikTok-optimized 8s/16s review scripts (Hook → Value → CTA)
- **UGC Video Styles** — Holding Product, Product Usage, UGC Review
- **Multi-Provider** — Kling, Runway, Pika, Minimax
- **Face Consistency** — Reference image support for consistent characters
- **Auto Download** — Download generated videos with proper naming

## 💰 Economics
| Item | Cost |
|------|------|
| Script generation (DeepSeek) | ~$0.0001/script |
| Video gen (Kling standard) | ~$0.15/video |
| Video gen (Runway Gen3) | ~$0.10/video |
| Total per UGC video | ~$0.10-0.15 |

## 📦 Integration
- Standalone microservice (port 8105)
- API-driven — no browser extension needed
- Can be called from ERP Modular or Etsy Wizard
