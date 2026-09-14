"""pipeline package — split from pipeline_affiliate.py (Phase C).

Re-exports the full public + helper surface so existing imports keep working.
"""
from ._shared import *  # noqa: F401,F403
from .providers import *  # noqa: F401,F403
from .prompts import *  # noqa: F401,F403
from .script import *  # noqa: F401,F403
from .recipes import *  # noqa: F401,F403
from .image import *  # noqa: F401,F403
from .video import *  # noqa: F401,F403
from .compose import *  # noqa: F401,F403
from .orchestrator import *  # noqa: F401,F403
