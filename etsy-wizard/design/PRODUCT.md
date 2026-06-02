# Etsy Wizard / Shop Assistant

> AI-powered Etsy Shop Setup Wizard — Mini MVP

## What it does

- **Wizard Flow**: Step-by-step shop setup (name → banner → about → policies → listings → photos → review)
- **Rules Validator**: Check every listing/image/policy against Etsy rules
- **AI Assistant**: Help write listings, descriptions, tags, shop policies
- **API Ready**: When Etsy API is granted → push to live shop

## Who uses it

| Role | Task |
|------|------|
| **Shop Owner (Pete)** | Set up shop, create listings, validate before publish |
| **AI Agent** | Generate listing content, check rules, suggest improvements |

## Architecture

```
etsy-wizard (port 8104)
├── /health              ← Health check
├── /validate/*          ← Etsy Rules Validator
├── /wizard/*            ← Shop Setup Flow
├── /listing/*           ← Listing Draft Manager
└── [future] /publish/*  ← Push to Etsy API
```

## Integration

- **ERP MCP**: Sync products/inventory (future)
- **ERP Modular Gateway**: Register as Mini App
- **Standalone** throughout — no dependencies on core files
