from pipeline import Step, PipelineContext

def create_step() -> Step:
    s = Step(
        name="image_prompt",
        desc="Build image gen prompt from profile + ugc_style — uses image_description from model_cast",
        requires=["product_name", "_normalized_age", "target_gender", "category"],
        outputs=["image_prompt", "neg_from_template"],
        help_text="Requires: product_name, _normalized_age, target_gender, category, ugc_style. Uses image_description, persona_clothing, persona_hair.",
    )
    async def run(ctx):
        from prompt_builder import build_image_prompt
        profile = ctx.ctx
        product_name = ctx.ctx["product_name"]
        ugc_style = ctx.ctx.get("ugc_style", "holding")
        ip, neg = build_image_prompt(profile, product_name, ugc_style)
        ctx.set_outputs(image_prompt=ip, neg_from_template=neg)
    s.run = run
    return s
