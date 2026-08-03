from pipeline import Step, PipelineContext

def create_step() -> Step:
    s = Step(
        name="product_analysis",
        desc="Analyze product_name + description via Gemini → category, audience, problem, benefit, product_appearance, features, router_config",
        requires=["product_name"],
        outputs=["analysis_profile", "category", "target_gender", "target_age", "target_audience", "image_description",
                 "setting", "customer_problem", "main_benefit", "hashtags",
                 "product_appearance", "features", "env_context", "product_type", "colors",
                 "router_config"],
        help_text="Requires: product_name. Optional: description, keywords. Calls Gemini text analysis + Router Agent.",
    )
    async def run(ctx):
        from prompt_builder import analyze_product
        product_name = ctx.ctx["product_name"]
        description = ctx.ctx.get("description", "")
        keywords = ctx.ctx.get("keywords", [])
        profile = analyze_product(product_name, description, keywords)
        router_config = profile.get("router_config", {})
        ctx.set_outputs(
            analysis_profile=profile,
            category=profile.get("category", "other"),
            target_gender=profile.get("target_gender", "person"),
            target_age=profile.get("target_age", ""),
            target_audience=profile.get("target_audience", ""),
            setting=profile.get("setting", ""),
            customer_problem=profile.get("customer_problem", ""),
            main_benefit=profile.get("main_benefit", ""),
            hashtags=profile.get("hashtags", []),
            product_appearance=profile.get("product_appearance", ""),
            features=profile.get("features", ""),
            env_context=profile.get("env_context", ""),
            product_type=profile.get("product_type", ""),
            colors=profile.get("colors", ""),
            router_config=router_config,
            image_description=profile.get("image_description", ""),
        )
    s.run = run
    return s

