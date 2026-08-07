from pipeline import Step, PipelineContext

def create_step() -> Step:
    s = Step(
        name="gender_fallback",
        desc="Ensure target_gender is only female/male; empty if unknown — never invented.",
        requires=[],
        outputs=["target_gender"],
        help_text="Always runs. Keeps only female/male; any other value becomes empty.",
    )
    async def run(ctx):
        gender = ctx.ctx.get("target_gender", "")
        if gender not in ("female", "male"):
            ctx.ctx["target_gender"] = ""
    s.run = run
    return s
