# TikTok UGC Studio — Design System

## Brand
- **Name:** TikTok UGC Studio
- **Tagline:** Realistic UGC Videos, Automated
- **Emoji:** 🎬

## API Design
```
POST /scripts/generate       — Generate TikTok review script
POST /scripts/ugc            — Generate UGC video prompt by style
GET  /scripts/variations     — Get hook/tone/CTA variations
GET  /scripts/templates      — List available templates
POST /video/generate        — Start video generation
POST /video/status          — Check video generation status
GET  /video/providers       — List available providers
GET  /prompts/list          — List all prompt files
GET  /prompts/{path}        — Get specific prompt
```

## Data Flow
```
Product Info → AI Script Generator → TikTok Script (Hook→Value→CTA)
                                  ↓
UGC Style + Face Ref → Video Gen Pipeline → AI Video
                                  ↓
                                  Download / Publish
```

## Color Palette
- Primary: #FF0050 (TikTok Red)
- Secondary: #00F2EA (TikTok Cyan)
- Dark: #161616
- Light: #FFFFFF
