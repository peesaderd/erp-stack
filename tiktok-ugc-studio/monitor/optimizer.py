"""Content optimizer — analyzes performance and adjusts strategy.

Feeds insights back into the content pipeline to improve
hook types, CTAs, templates, posting times, and hashtags."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger("monitor.optimizer")

STRATEGY_FILE = Path(__file__).parent.parent / "storage" / "strategy.json"

DEFAULT_STRATEGY = {
    "hook_type": "problem",
    "cta_style": "link_in_bio",
    "preferred_template": "problem_solution",
    "posting_hours": [9, 12, 15, 18, 21],
    "posting_timezone": "Asia/Bangkok",
    "hashtag_count": 3,
    "hashtag_strategy": "trending",
    "sound_vibe": "upbeat_excited",
    "target_duration_sec": 28,
    "pacing": "fast",
    "content_mix": {
        "product_review": 0.5,
        "before_after": 0.2,
        "tutorial": 0.15,
        "testimonial": 0.15,
    },
    "version": 1,
    "updated_at": None,
}


def _load_strategy() -> dict:
    """Load current content strategy from storage."""
    if STRATEGY_FILE.exists():
        try:
            with open(STRATEGY_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            pass
    return dict(DEFAULT_STRATEGY)


def _save_strategy(strategy: dict):
    """Save updated strategy."""
    STRATEGY_FILE.parent.mkdir(parents=True, exist_ok=True)
    strategy["updated_at"] = datetime.now(timezone.utc).isoformat()
    strategy["version"] = strategy.get("version", 0) + 1
    with open(STRATEGY_FILE, "w") as f:
        json.dump(strategy, f, indent=2, default=str)


async def get_strategy() -> dict:
    """Get current content strategy."""
    return _load_strategy()


async def reset_strategy() -> dict:
    """Reset strategy to defaults."""
    strategy = dict(DEFAULT_STRATEGY)
    _save_strategy(strategy)
    return strategy


async def update_strategy(updates: dict) -> dict:
    """Apply partial updates to the strategy."""
    strategy = _load_strategy()
    _deep_merge(strategy, updates)
    _save_strategy(strategy)
    return strategy


async def analyze_and_optimize(
    performance_data: dict,
    current_strategy: Optional[dict] = None,
) -> dict:
    """Analyze performance data and generate strategy optimizations.

    This is the core of the monitor loop — takes video performance
    metrics and adjusts the content strategy accordingly.
    """
    if current_strategy is None:
        current_strategy = _load_strategy()

    recommendations = []
    changes = {}

    # 1. Analyze posting time performance
    time_recommendation = _optimize_posting_times(
        performance_data.get("videos_by_hour", {}),
        current_strategy.get("posting_hours", []),
    )
    if time_recommendation:
        recommendations.append(time_recommendation)
        if time_recommendation.get("new_hours"):
            changes["posting_hours"] = time_recommendation["new_hours"]

    # 2. Analyze hook type performance
    hook_rec = _optimize_hook_type(
        performance_data.get("hooks_performance", {}),
        current_strategy.get("hook_type", "problem"),
    )
    if hook_rec:
        recommendations.append(hook_rec)
        if hook_rec.get("new_hook_type"):
            changes["hook_type"] = hook_rec["new_hook_type"]

    # 3. Analyze template performance
    template_rec = _optimize_template(
        performance_data.get("templates_performance", {}),
        current_strategy.get("preferred_template", "problem_solution"),
    )
    if template_rec:
        recommendations.append(template_rec)
        if template_rec.get("new_template"):
            changes["preferred_template"] = template_rec["new_template"]

    # 4. Analyze content mix
    mix_rec = _optimize_content_mix(
        performance_data.get("category_performance", {}),
        current_strategy.get("content_mix", {}),
    )
    if mix_rec:
        recommendations.append(mix_rec)
        if mix_rec.get("new_mix"):
            changes["content_mix"] = mix_rec["new_mix"]

    # 5. Generate overall insights
    insights = _generate_insights(performance_data, changes)

    # Apply changes if any
    if changes:
        strategy = _load_strategy()
        _deep_merge(strategy, changes)
        _save_strategy(strategy)
        logger.info(f"Strategy updated: {changes}")

    return {
        "changes_applied": bool(changes),
        "changes": changes,
        "recommendations": recommendations,
        "insights": insights,
        "strategy": _load_strategy(),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


def _deep_merge(base: dict, updates: dict):
    """Recursively merge updates into base dict."""
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _optimize_posting_times(
    hourly_performance: dict,
    current_hours: List[int],
) -> Optional[dict]:
    """Recommend optimal posting times based on performance data."""
    if not hourly_performance:
        return None

    # Sort hours by performance
    sorted_hours = sorted(
        hourly_performance.items(),
        key=lambda x: x[1].get("avg_views", 0),
        reverse=True,
    )

    if not sorted_hours:
        return None

    top_hours = [int(h) for h, _ in sorted_hours[:5]]
    top_hours.sort()

    # Only recommend if significantly different from current
    if top_hours != current_hours:
        return {
            "type": "posting_times",
            "reason": "ปรับเวลาลงตามเวลาที่มี engagement สูงสุด",
            "current": current_hours,
            "new_hours": top_hours,
            "expected_impact": "mid",
        }
    return None


def _optimize_hook_type(
    hooks_performance: dict,
    current_hook: str,
) -> Optional[dict]:
    """Recommend the best performing hook type."""
    if not hooks_performance:
        return None

    best_hook = max(
        hooks_performance.items(),
        key=lambda x: x[1].get("avg_views", 0),
    )

    if best_hook[0] != current_hook and best_hook[1].get("avg_views", 0) > 100:
        return {
            "type": "hook_type",
            "reason": f'Hook "{best_hook[0]}" มี engagement สูงกว่า',
            "current": current_hook,
            "new_hook_type": best_hook[0],
            "confidence": round(best_hook[1].get("avg_views", 0) / 1000, 2),
            "expected_impact": "high",
        }
    return None


def _optimize_template(
    templates_performance: dict,
    current_template: str,
) -> Optional[dict]:
    """Recommend the best performing template."""
    if not templates_performance:
        return None

    best_tpl = max(
        templates_performance.items(),
        key=lambda x: x[1].get("avg_views", 0),
    )

    if best_tpl[0] != current_template:
        return {
            "type": "template",
            "reason": f'Template "{best_tpl[0]}" มี view เฉลี่ยสูงกว่า',
            "current": current_template,
            "new_template": best_tpl[0],
            "expected_impact": "high",
        }
    return None


def _optimize_content_mix(
    category_performance: dict,
    current_mix: dict,
) -> Optional[dict]:
    """Adjust content mix based on category performance."""
    if not category_performance:
        return None

    total_views = sum(v.get("avg_views", 0) for v in category_performance.values())
    if total_views == 0:
        return None

    # Calculate new mix based on proportional performance
    new_mix = {}
    for cat, data in category_performance.items():
        share = data.get("avg_views", 0) / total_views
        if share > 0.05:  # Only include meaningful shares
            new_mix[cat] = round(share, 2)

    if not new_mix:
        return None

    # Normalize
    total = sum(new_mix.values())
    if total > 0:
        new_mix = {k: round(v / total, 2) for k, v in new_mix.items()}

    if new_mix != current_mix:
        return {
            "type": "content_mix",
            "reason": "ปรับสัดส่วนคอนเทนต์ตาม performance",
            "current": current_mix,
            "new_mix": new_mix,
            "expected_impact": "medium",
        }
    return None


def _generate_insights(performance_data: dict, changes: dict) -> List[str]:
    """Generate human-readable insights from performance data."""
    insights = []

    summary = performance_data.get("summary", {})
    if summary:
        avg_views = summary.get("avg_views", 0)
        if avg_views > 5000:
            insights.append(f"🔥 ฟอร์มดี! view เฉลี่ย {avg_views:,.0f} — เดินหน้าต่อ")
        elif avg_views > 1000:
            insights.append(f"👍 view เฉลี่ย {avg_views:,.0f} — ยังปรับปรุงได้")
        else:
            insights.append(f"📉 view ต่ำ ({avg_views:,.0f}) — ต้องปรับกลยุทธ์ครั้งใหญ่")

        best = summary.get("best_video", {})
        if best and best.get("views", 0) > 10000:
            insights.append(
                f'🏆 คลิปปัง: "{best.get("caption", "")[:40]}..." '
                f'{best.get("views", 0):,} views'
            )

    if changes:
        insights.append(f"🔄 ปรับกลยุทธ์ {len(changes)} จุด — รอดูผลรอบถัดไป")
    else:
        insights.append("📊 ข้อมูลยังไม่พอปรับกลยุทธ์ — เก็บ data ต่อ")

    return insights
