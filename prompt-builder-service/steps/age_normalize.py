from pipeline import Step, PipelineContext

def create_step() -> Step:
    s = Step(
        name="age_normalize",
        desc="Normalize target_age range → single int (0 if absent) for consistent age in prompts",
        requires=["target_age"],
        outputs=["_normalized_age"],
        help_text="Requires: target_age from analysis. Outputs normalized int (0 if absent).",
    )
    async def run(ctx):
        from prompt_builder import _normalize_age
        ctx.ctx["_normalized_age"] = _normalize_age(ctx.ctx["target_age"])
    s.run = run
    return s
