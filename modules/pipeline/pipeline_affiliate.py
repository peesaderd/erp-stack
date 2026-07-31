"""
Single source of truth: modules/video/pipeline_affiliate.py
"""
import sys
import importlib.util
from pathlib import Path

_real = Path(__file__).resolve().parent.parent / "video" / "pipeline_affiliate.py"
spec = importlib.util.spec_from_file_location("_pipeline_affiliate_real", str(_real))
_mod = importlib.util.module_from_spec(spec)
sys.modules["_pipeline_affiliate_real"] = _mod
spec.loader.exec_module(_mod)

# Re-export everything
__all__ = getattr(_mod, "__all__", [])
for _attr in dir(_mod):
    if not _attr.startswith("_"):
        globals()[_attr] = getattr(_mod, _attr)
