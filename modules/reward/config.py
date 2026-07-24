"""
Reward Module — Configuration
"""
import os

# ── Service ──
HOST = os.environ.get("REWARD_HOST", "0.0.0.0")
PORT = int(os.environ.get("REWARD_PORT", "8121"))

# ── Schema Engine ──
SCHEMA_ENGINE_URL = os.environ.get("SCHEMA_ENGINE_URL", "http://localhost:8100")

# ── External Services ──
ERP_MODULAR_URL = os.environ.get("ERP_MODULAR_URL", "http://localhost:8102")
POS_API_URL = os.environ.get("POS_API_URL", "http://localhost:8114")

# ── Tier Configuration ──
TIERS = {
    "bronze": {
        "label": "🥉 Bronze",
        "min_points": 0,
        "multiplier": 1.0,  # 1x points earn rate
        "color": "#CD7F32",
    },
    "silver": {
        "label": "🥈 Silver",
        "min_points": 500,
        "multiplier": 1.2,
        "color": "#C0C0C0",
    },
    "gold": {
        "label": "🥇 Gold",
        "min_points": 2000,
        "multiplier": 1.5,
        "color": "#FFD700",
    },
    "platinum": {
        "label": "💎 Platinum",
        "min_points": 10000,
        "multiplier": 2.0,
        "color": "#E5E4E2",
    },
}

# ── Earning Rules (default) ──
DEFAULT_EARN_RATE = 10        # 1 point per 10 baht spent
BONUS_ON_REGISTER = 100       # sign-up bonus
BONUS_ON_BIRTHDAY = 100       # birthday bonus
MAX_EARN_PER_DAY = 10000      # max points earnable per day

# ── Schema Slugs ──
SCHEMA_MEMBER = "member"
SCHEMA_REWARD_LEDGER = "reward_ledger"
SCHEMA_REWARDS = "rewards"
