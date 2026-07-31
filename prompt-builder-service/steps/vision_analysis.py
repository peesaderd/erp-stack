from pipeline import Step, PipelineContext

def create_step() -> Step:
    s = Step(
        name="vision_analysis",
        desc="Analyze product_image URL via Gemini Vision → enrich product_appearance, features, env_context, colors",
        requires=["product_name"],
        outputs=["category", "target_gender", "target_age", "target_audience", "setting",
                 "customer_problem", "main_benefit", "env_context", "product_appearance",
                 "features", "product_type", "colors"],
        allow_failure=True,
        help_text="Optional. Requires: product_image URL. Falls back gracefully if image URL is missing or external.",
    )
    async def run(ctx):
        product_image = ctx.ctx.get("product_image", "")
        if not product_image:
            ctx.set_outputs(_step_vision_analysis_error="No product_image URL provided — skipped")
            return
        from gemini_client import analyze_product_image
        product_name = ctx.ctx["product_name"]
        description = ctx.ctx.get("description", "")
        vision_profile = analyze_product_image(product_image, product_name, description)
        if vision_profile:
            for key in ["category", "target_gender", "target_age", "target_audience", "setting",
                         "customer_problem", "main_benefit", "env_context", "product_appearance", "features"]:
                if key in vision_profile and vision_profile[key]:
                    ctx.ctx[key] = vision_profile[key]
            if "product_type" in vision_profile and vision_profile["product_type"]:
                ctx.ctx["product_type"] = vision_profile["product_type"]
            if "colors" in vision_profile and vision_profile["colors"]:
                ctx.ctx["colors"] = vision_profile["colors"]
    s.run = run
    return s
