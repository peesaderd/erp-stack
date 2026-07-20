# Task 2: Pipeline Recipe Templates

## Background
Current pipeline auto-selects bgm_style based on ugc_style (holding_product→upbeat_pop, product_usage→chill_loft, etc.). We want to add **recipe templates** that users can pick from in the frontend.

## Files to modify

### 1. `/home/openhands/erp-stack/tiktok-ugc-studio/main.py`

Add a recipe template system:

```python
# ── Recipe Templates ──
RECIPE_TEMPLATES = {
    "skincare": {
        "label": "🧴 Skincare Glow",
        "description": "Soft luxury vibes, calm music, slow transitions",
        "ugc_style": "product_usage",
        "sound_style": "luxury_jazz",
        "mood": "calm",
        "duration": 10,
        "scene_count": 2,
        "bgm_style": "luxury_jazz",
    },
    "gadget": {
        "label": "📱 Gadget Unboxing",
        "description": "Fast-paced, energetic, quick cuts",
        "ugc_style": "holding_product",
        "sound_style": "upbeat_pop",
        "mood": "energetic",
        "duration": 8,
        "scene_count": 1,
        "bgm_style": "upbeat_pop",
    },
    "fashion": {
        "label": "👗 Fashion Lookbook",
        "description": "Elegant slow-mo, chic aesthetic",
        "ugc_style": "talking_head",
        "sound_style": "chill_loft",
        "mood": "luxurious",
        "duration": 8,
        "scene_count": 1,
        "bgm_style": "chill_loft",
    },
    "food": {
        "label": "🍜 Food Review",
        "description": "Warm, ASMR-style, close-up shots",
        "ugc_style": "ugc_review",
        "sound_style": "asmr",
        "mood": "fun",
        "duration": 10,
        "scene_count": 2,
        "bgm_style": "asmr",
    },
    "asmr": {
        "label": "🎧 ASMR Unboxing",
        "description": "Quiet ambient, gentle sounds, relaxing",
        "ugc_style": "product_usage",
        "sound_style": "asmr",
        "mood": "calm",
        "duration": 12,
        "scene_count": 2,
        "bgm_style": "asmr",
    },
}
```

Add endpoint: `GET /pipeline/recipes` that returns recipe templates list.

### 2. Frontend `/home/openhands/erp-stack/tiktok-ugc-studio/frontend/public/index.html`

In the Content tab → Generate Video section, **replace** the existing style/bgm selection with a **Recipe Picker**:

#### Recipe cards (before the advanced options):
```html
<div id="recipePicker" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;margin-bottom:12px">
  <!-- populated by JS: recipe cards with emoji + label + description on hover -->
</div>
```

Each recipe card:
- Shows emoji + label + small description
- Highlighted when selected (like style cards)
- Clicking sets: ugc_style, sound_style, mood, duration, bgm_style based on recipe

#### JavaScript:
```javascript
async function loadRecipes() {
  const r = await fetch(API + '/pipeline/recipes');
  const d = await r.json();
  const recipes = d.recipes || [];
  const container = document.getElementById('recipePicker');
  container.innerHTML = recipes.map(r => `
    <div class="style-card${r.name === 'gadget' ? ' selected' : ''}" data-recipe="${r.name}"
         onclick="selectRecipe('${r.name}')" title="${r.description}">
      <div style="font-size:24px">${r.label.split(' ')[0]}</div>
      <div class="font-medium" style="font-size:12px">${r.label.replace(/^[^\s]+\s/, '')}</div>
      <div class="text-xs text-secondary">${r.description}</div>
    </div>
  `).join('');
}

function selectRecipe(name) {
  // Highlight recipe card
  document.querySelectorAll('#recipePicker .style-card').forEach(c => c.classList.remove('selected'));
  document.querySelector(`[data-recipe="${name}"]`)?.classList.add('selected');
  
  // Apply recipe settings to form
  // (This is done by storing the recipe name, which gets sent to API)
  document.getElementById('selectedRecipe').value = name;
}
```

Add a hidden input: `<input type="hidden" id="selectedRecipe" value="gadget">`

And in the generate API call, if `selectedRecipe` is set, use recipe settings as defaults (allow manual overrides).

### Important
- Don't break existing generate flow
- Recipe selection is a **shortcut** — user can still manually tweak after selecting recipe
- Keep existing style-select-grid for advanced customization below the recipe picker
- Make recipes responsive on mobile (2 columns)
