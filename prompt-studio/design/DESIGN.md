# Prompt Studio — Design

## API
GET  /health
GET  /modules                          — List all modules
GET  /prompts/{module}                 — List files in module
GET  /prompts/{module}/{name}          — Get prompt content
POST /prompts/fill                     — Fill {{placeholder}}
GET  /config                           — Show loader config
POST /admin/clear-cache                — Clear cache

## Transition Plan
1. Phase 1 (now):  Every service has local prompts + calls Prompt Studio
2. Phase 2:        Sync prompts to CDN (S3/Cloudflare R2)
3. Phase 3:        Set PROMPT_MODE=url + PROMPT_BASE_URL
4. Phase 4:        Remove local prompt files (optional)

## Color
- Primary: #8B5CF6 (Violet — representing "modular"/"connector")
- Secondary: #2DD4BF (Teal)
