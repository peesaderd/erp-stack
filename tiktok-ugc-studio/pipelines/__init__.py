# pipelines/__init__.py — Pipeline Template System
# Recipe × UGC Style → Pipeline Config → Wan 2.7 Generation

from .runner import (
    PipelineConfig,
    build_pipeline_config,
    list_templates,
    get_template,
)

__all__ = [
    "PipelineConfig",
    "build_pipeline_config",
    "list_templates", 
    "get_template",
]
