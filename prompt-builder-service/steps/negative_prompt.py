from pipeline import Step, PipelineContext

def create_step() -> Step:
    s = Step(
        name="negative_prompt",
        desc="Build negative prompt, merging template negation + default negation",
        requires=[],
        outputs=["negative_prompt"],
        help_text="Always runs. Merges neg_from_template (if any) with default negative.",
    )
    async def run(ctx):
        from prompt_builder import build_negative_prompt
        profile = ctx.ctx
        ugc_style = ctx.ctx.get("ugc_style", "holding")
        neg_from_template = ctx.ctx.get("neg_from_template", "")
        default_neg = build_negative_prompt(profile, ugc_style)
        if neg_from_template:
            ctx.ctx["negative_prompt"] = f"{neg_from_template}, {default_neg}"
        else:
            ctx.ctx["negative_prompt"] = default_neg
    s.run = run
    return s
