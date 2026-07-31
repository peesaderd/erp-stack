# ─── Prompt Pipeline Engine ───────────────────────────────────────
#  Orchestrates prompt generation as explicit, traceable steps.
#  Each step declares required inputs, outputs, and failure policy.
#  Agents introspect via GET /api/v1/pipeline/steps.
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations
import time, traceback, logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("prompt-pipeline")

# ═══════════════════════════════════════════════════════════════════
# ─── Pipeline Context ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════

class PipelineContext:
    """Mutable context that flows through every step of the pipeline."""

    def __init__(self, inputs: Dict[str, Any]):
        self.ctx: Dict[str, Any] = dict(inputs)
        self.history: List[Dict[str, Any]] = []
        self.started_at: float = time.time()

    def require(self, *keys: str):
        """Assert that ``keys`` are present in ctx. Raises PipelineMissingInput."""
        missing = [k for k in keys if k not in self.ctx or self.ctx[k] is None]
        if missing:
            raise PipelineMissingInput(list(self.ctx.keys()), missing)

    def set_outputs(self, **kwargs):
        """Merge outputs into ctx."""
        self.ctx.update(kwargs)

    def snapshot(self) -> dict:
        return {
            "ctx_keys": sorted(self.ctx.keys()),
            "history": [h["name"] for h in self.history],
            "elapsed_sec": round(time.time() - self.started_at, 3),
        }


# ═══════════════════════════════════════════════════════════════════
# ─── Step ─────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════

class Step:
    """One step in the pipeline.

    :param name:   human-readable short name (e.g. "model_cast")
    :param desc:   one-line description shown to agents
    :param requires: keys that MUST exist in ctx before this step runs
    :param outputs: keys this step writes into ctx
    :param allow_failure: if True, exceptions are logged but pipeline continues
    :param help_text: shown to agents / in error responses when step fails
    """

    def __init__(
        self,
        name: str,
        desc: str = "",
        requires: Optional[List[str]] = None,
        outputs: Optional[List[str]] = None,
        allow_failure: bool = False,
        help_text: str = "",
    ):
        self.name = name
        self.desc = desc
        self.requires = requires or []
        self.outputs = outputs or []
        self.allow_failure = allow_failure
        self.help_text = help_text

    async def run(self, ctx: PipelineContext) -> None:
        raise NotImplementedError(f"Step '{self.name}' has no run() implementation")

    def describe(self) -> dict:
        return {
            "name": self.name,
            "description": self.desc,
            "requires": self.requires,
            "outputs": self.outputs,
            "allow_failure": self.allow_failure,
            "help": self.help_text,
        }


# ═══════════════════════════════════════════════════════════════════
# ─── Pipeline ─────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════

class Pipeline:
    """Ordered list of steps executed sequentially with shared context."""

    def __init__(self, name: str, steps: List[Step]):
        self.name = name
        self.steps = steps

    def describe(self) -> dict:
        return {
            "pipeline": self.name,
            "total_steps": len(self.steps),
            "steps": [
                {"index": i + 1, **s.describe()}
                for i, s in enumerate(self.steps)
            ],
        }

    async def run(self, inputs: Dict[str, Any]) -> PipelineContext:
        ctx = PipelineContext(inputs)
        logger.info(f"┌─ Pipeline '{self.name}' started — {len(self.steps)} steps")

        for i, step in enumerate(self.steps, 1):
            tag = f"[Step {i}/{len(self.steps)} {step.name}]"
            try:
                # Validate required inputs
                ctx.require(*step.requires)
            except PipelineMissingInput as e:
                msg = (
                    f"{tag} MISSING INPUT — needs {e.missing}, "
                    f"but ctx has {e.available}"
                )
                logger.error(msg)
                raise PipelineError(
                    step=step.name, index=i,
                    reason=f"Missing required inputs: {e.missing}",
                    ctx_snapshot=ctx.snapshot(),
                    help=step.help_text,
                ) from e

            try:
                t0 = time.time()
                await step.run(ctx)
                elapsed = round(time.time() - t0, 3)

                ctx.history.append({
                    "index": i, "name": step.name, "status": "ok", "elapsed": elapsed,
                })
                logger.info(
                    f"{tag} ✓ OK ({elapsed}s) — ctx keys now: {sorted(ctx.ctx.keys())}"
                )

            except Exception as e:
                ctx.history.append({
                    "index": i, "name": step.name, "status": "error",
                    "reason": str(e)[:200],
                })

                if step.allow_failure:
                    logger.warning(
                        f"{tag} ⚠ SKIPPED (allow_failure=True) — {e}"
                    )
                    ctx.ctx[f"_step_{step.name}_error"] = str(e)[:500]
                    continue

                logger.error(f"{tag} ✗ FAIL — {e}")
                raise PipelineError(
                    step=step.name, index=i,
                    reason=str(e)[:500],
                    ctx_snapshot=ctx.snapshot(),
                    help=step.help_text,
                ) from e

        elapsed_total = round(time.time() - ctx.started_at, 3)
        logger.info(f"└─ Pipeline '{self.name}' DONE ({elapsed_total}s)")
        return ctx


# ═══════════════════════════════════════════════════════════════════
# ─── Pipeline Errors ──────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════

class PipelineMissingInput(Exception):
    """Raised when a required key is missing from context."""
    def __init__(self, available: List[str], missing: List[str]):
        self.available = available
        self.missing = missing
        super().__init__(f"Missing inputs: {missing}. Available: {available}")


class PipelineError(Exception):
    """Rich, debuggable error from a pipeline step."""

    def __init__(
        self,
        step: str,
        index: int,
        reason: str,
        ctx_snapshot: Optional[dict] = None,
        help: str = "",
    ):
        self.step = step
        self.index = index
        self.reason = reason
        self.ctx_snapshot = ctx_snapshot or {}
        self.help = help
        super().__init__(
            f"[Step {index} '{step}'] {reason}"
        )

    def to_dict(self) -> dict:
        return {
            "error": str(self),
            "step": {"index": self.index, "name": self.step},
            "reason": self.reason,
            "context_snapshot": self.ctx_snapshot,
            "help": self.help,
        }
