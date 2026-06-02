# Prompt Studio

## Vision
Central prompt repository for all AI microservices. 
Abstracts prompt storage behind a clean API so any service can load prompts without knowing where they live.

## Architecture
- Current: local file storage (PROMPT_MODE=file)
- Future: CDN/URL-based (PROMPT_MODE=url + PROMPT_BASE_URL)
- Clients load via API not filesystem
- Cache layer to reduce network calls

## Modules
- tiktok/ — TikTok review script prompts (AiBot v4.5)
- ugc/ — UGC video prompts (Holding, Usage, Review)
- image/ — Image generation prompts
- video/ — Video gen prompts (future)
