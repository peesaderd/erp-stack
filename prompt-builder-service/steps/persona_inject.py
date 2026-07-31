from pipeline import Step, PipelineContext

def create_step() -> Step:
    s = Step(
        name="persona_inject",
        desc="Select random persona (energetic_young, calm_professional, mom_at_home, etc.) by category → inject vibe, environment, clothing, hair, lighting, motion",
        requires=["category"],
        outputs=["persona_vibe", "persona_environment", "persona_lighting", "persona_motion",
                 "persona_clothing", "persona_hair", "persona_age"],
        help_text="Requires: category. Diversity via random persona selection.",
    )
    async def run(ctx):
        from persona_engine import _select_persona, _apply_persona_to_profile
        category = ctx.ctx["category"]
        product_name = ctx.ctx.get("product_name", "")
        profile = dict(ctx.ctx)
        persona = _select_persona(category, product_name)
        profile = _apply_persona_to_profile(profile, persona)
        ctx.set_outputs(
            persona_vibe=profile.get("persona_vibe", persona.get("vibe", "")),
            persona_environment=profile.get("setting", persona.get("environment", "")),
            persona_lighting=profile.get("persona_lighting", persona.get("lighting_variation", "")),
            persona_motion=profile.get("persona_motion", persona.get("motion_speed", "")),
            persona_clothing=profile.get("persona_clothing", ""),
            persona_hair=profile.get("persona_hair", ""),
            persona_age=profile.get("persona_age", ""),
        )
        ctx.ctx["persona_vibe"] = profile.get("persona_vibe", persona.get("vibe", ""))
        ctx.ctx["persona_clothing"] = profile.get("persona_clothing", "")
        ctx.ctx["persona_hair"] = profile.get("persona_hair", "")
        ctx.ctx["persona_environment"] = profile.get("setting", persona.get("environment", ""))
    s.run = run
    return s
