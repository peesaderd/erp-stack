from pipeline import Step, PipelineContext

def create_step() -> Step:
    s = Step(
        name="timing_validation",
        desc="Build script hook/value/CTA + validate timing fits within 8s total",
        requires=["product_name", "category"],
        outputs=["timing_validation", "scripts_breakdown", "tts_script", "full_script"],
        help_text="Requires: product_name, category. Optional: customer_problem, main_benefit, target_gender.",
    )
    async def run(ctx):
        from prompt_builder import _build_timing_validated_script
        product_name = ctx.ctx["product_name"]
        category = ctx.ctx.get("category", "beauty")
        timing = _build_timing_validated_script(product_name, category, ctx.ctx)
        ctx.set_outputs(
            timing_validation=timing,
            scripts_breakdown={"hook": timing["hook"]["text"], "value": timing["value"]["text"], "cta": timing["cta"]["text"]},
            tts_script=timing["tts_script"],
            full_script=timing["full_script"],
        )
    s.run = run
    return s
