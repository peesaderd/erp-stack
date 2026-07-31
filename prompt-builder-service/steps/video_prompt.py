from pipeline import Step, PipelineContext

def create_step() -> Step:
    s = Step(
        name="video_prompt",
        desc="Build video gen prompt from profile + ugc_style — uses image_description from model_cast",
        requires=["product_name", "_normalized_age", "target_gender", "category"],
        outputs=["video_prompt"],
        help_text="Requires: product_name, _normalized_age, target_gender, category, ugc_style. Uses image_description, persona_clothing, persona_hair.",
    )
    async def run(ctx):
        from prompt_builder import build_video_prompt
        profile = ctx.ctx
        product_name = ctx.ctx["product_name"]
        ugc_style = ctx.ctx.get("ugc_style", "holding")
        vp = build_video_prompt(profile, product_name, ugc_style)
        ctx.set_outputs(video_prompt=vp)
    s.run = run
    return s
