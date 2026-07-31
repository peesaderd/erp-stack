from pipeline import Step, PipelineContext

def create_step() -> Step:
    s = Step(
        name="model_cast",
        desc="Draw random Thai model (12 casts) without replacement — provides image_description used in prompts",
        requires=["category", "product_name"],
        outputs=["image_description", "model_appearance", "model_id"],
        help_text="REQUIRED. Uses model_casting.select_model_cast() — 12 Thai models, draw-without-replacement (last 3 excluded).",
    )
    async def run(ctx):
        from model_casting import select_model_cast
        category = ctx.ctx["category"]
        product_name = ctx.ctx["product_name"]
        mc = select_model_cast(category, product_name)
        ctx.set_outputs(
            image_description=mc.get("image_description", ""),
            model_appearance=mc.get("model_appearance_th", ""),
            model_id=mc.get("model_id", ""),
        )
    s.run = run
    return s
