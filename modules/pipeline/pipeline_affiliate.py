"""
Thin wrapper — single source of truth is modules/video/pipeline_affiliate.py
"""
import sys
from pathlib import Path

# Ensure video module is importable
_video = Path(__file__).parent.parent / "video"
if str(_video) not in sys.path:
    sys.path.insert(0, str(_video))

from pipeline_affiliate import *  # noqa: E402, F403
