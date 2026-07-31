from pipeline import Step, PipelineContext

def create_step() -> Step:
    s = Step(
        name="gender_fallback",
        desc="Ensure target_gender is specific (not 'unisex' or empty). Falls back to 'female'.",
        requires=[],
        outputs=["target_gender"],
        help_text="Always runs. Normalizes target_gender → female if unisex/empty.",
    )
    async def run(ctx):
        gender = ctx.ctx.get("target_gender", "")
        if gender in ("unisex", "", None):
            ctx.ctx["target_gender"] = "female"
    s.run = run
    return s
