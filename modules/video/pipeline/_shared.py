"""Shared config, paths, imports & logger for the pipeline package.

Extracted from pipeline_affiliate.py header (Phase C split, move-only).
"""
import os
import re
import sys
import json
import time
import uuid
import logging
import random
import subprocess
import shutil
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests

# Add erp-stack to path for shared_config
_erp_stack = Path(__file__).resolve().parent.parent.parent.parent  # erp-stack
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from shared_config import PRODIA_TOKEN, GEMINI_API_KEY

# ─── Schema Engine UGC Style Client ─────────────────────────────────
_ugc_client_dir = os.path.join(str(_erp_stack), "prompt-builder-service")
if _ugc_client_dir not in sys.path:
    sys.path.insert(0, _ugc_client_dir)
from ugc_schema_client import get_default_style, get_style_config, validate_ugc_style, is_valid_style

# Import pipeline logger (same directory as this package's parent)
_parent_dir = str(Path(__file__).resolve().parent.parent)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)
from pipeline_logger import start_job, update_step, update_cost, complete_job, fail_job, update_prompts

logger = logging.getLogger("tiktok-ugc.pipeline_affiliate")

# ─── Config ────────────────────────────────────────────────────────────────

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
TMP_DIR = STORAGE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# Service URLs
IMAGE_GEN_URL = "http://localhost:8110/api/v1/image/generate"
PROMPT_BUILDER_URL = "http://localhost:8117"
