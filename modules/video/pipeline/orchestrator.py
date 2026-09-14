"""Full pipeline orchestration (Phase C split, move-only)."""
from ._shared import (  # noqa: F401
    os, re, sys, json, time, uuid, logging, random, subprocess, shutil, asyncio,
    Path, Optional, List, Dict, Any, requests,
    PRODIA_TOKEN, GEMINI_API_KEY, logger,
    IMAGE_GEN_URL, PROMPT_BUILDER_URL, STORAGE_DIR, TMP_DIR,
    get_default_style, get_style_config, validate_ugc_style, is_valid_style,
    start_job, update_step, update_cost, complete_job, fail_job, update_prompts, get_job,
)
from .providers import (
    _extract_json_obj, _deepseek_key, _mimo_key, _mimo_image_ref,
    _hue_diverse_reference_index, _pick_variant_reference_index,
)
from .prompts import (
    _deepseek_product_prompts, _normalize_negative_prompt, _sanitize_video_prompt,
    is_wearable,
)
from .script import analyze_product, generate_script, _synthesize_script_beats
from .prompts import _normalize_script_beats
from .recipes import load_recipe
from .image import (build_image_prompt, generate_image, _build_klein_last_prompt,
                    generate_klein_last_image, _clean_product_name_for_video)
from .video import generate_video, _generate_fallback_video_from_image, has_audio_track
from .compose import compose_video, concat_videos, get_bgm_path, download_file

# ═══════════════════════════════════════════════════════════════════════════
# MAIN: Run Full Pipeline v6
# ═══════════════════════════════════════════════════════════════════════════

def run_pipeline(
    product_name: str,
    product_image: Optional[str] = None,
    recipe_name: str = "tus",
    voice: str = "Aoede",
    bgm_style: str = "chill_loft",
    description: Optional[str] = None,
    ugc_style: str = "holding",
    external_job_id: Optional[str] = None,
    product_images: Optional[list] = None,
    duration: int = 15,
    image_prompt: Optional[str] = None,
    video_prompt: Optional[str] = None,
    video_prompts: Optional[list] = None,
    negative_prompt: Optional[str] = None,
    script: Optional[str] = None,
    # ── First/Reference/Last frame + Thai script (Wan พูดเอง ไม่ใช้ TTS lip-sync ทับ) ──
    first_frame: Optional[str] = None,
    reference_image: Optional[str] = None,
    last_frame: Optional[str] = None,
    thai_script: Optional[str] = None,
    use_tus_voice: bool = True,
    audio_path: Optional[str] = None,
    prompt_extend: bool = False,
    gender: str = "female",
    age: str = "",
    **kwargs,
) -> dict:
    """
    Run full Affiliate Pipeline v6 (9 Steps ตาม PIPELINE_STRUCTURE.md)

    Args:
        product_name: ชื่อสินค้า
        product_image: URL ของรูปสินค้า (required!)
        recipe_name: ชื่อ recipe (tus, etsy)
        voice: ชื่อเสียง TTS
        bgm_style: สไตล์เพลงพื้นหลัง
        description: คําอธิบายสินค้า (optional)
        external_job_id: job_id จาก caller (ถ้ามี) — ใช้แทนการ gen เอง เพื่อให้ pipeline_logs.db
                         ตรงกับ pipeline.db ใน tiktok-ugc-studio
        image_prompt: รูป prompt ที่เตรียมมาแล้ว (ถ้ามีจะไม่ gen ใหม่)
        video_prompt: วิดีโอ prompt ที่เตรียมมาแล้ว (ใช้ fallback ถ้า video_prompts ไม่มี)
        video_prompts: รายการวิดีโอ prompts ต่อ scene (ถ้ามีจะไม่ gen ใหม่)
        negative_prompt: negative prompt ที่เตรียมมาแล้ว
        script: script ที่เตรียมมาแล้ว (ถ้ามีจะไม่ gen ใหม่)
        first_frame: path/URL ของ first frame image (ใช้แทน image ที่ gen สำหรับ Wan)
        reference_image: path/URL ของ reference image (ส่งให้ Wan เป็น reference)
        last_frame: path/URL ของ target last-frame image (Wan 2.7 start-end interpolation)
        thai_script: บทพูดภาษาไทยที่ให้ Wan พูดเองในคลิป (ไม่ใช้ TTS lip-sync ทับ)
        use_tus_voice: DEPRECATED (ทิศทางเก่า "ให้ Wan พูดเอง" ปิดแล้ว 2026-08-15) —
            เก็บไว้รับค่า backward-compat เท่านั้น ไม่มีผลต่อ pipeline แล้ว
            ทิศทางใหม่: ส่ง TTS audio ให้ Wan เสมอ (lip-sync) + TTS/BGM ทับที่ compose

    Returns:
        dict: {
            run_id, final_path, duration, cost_estimate, cost_breakdown,
            product_profile, recipe, script, image_path, video_paths
        }
    """
    run_id = uuid.uuid4().hex[:8]
    job_id = external_job_id or f"vid_{run_id}"

    logger.info(f"{'='*60}")
    logger.info(f"Pipeline v6 - Run {run_id}")
    logger.info(f"{'='*60}")
    logger.info(f"Product: {product_name}")
    logger.info(f"Image: {product_image}")
    logger.info(f"Recipe: {recipe_name}")
    logger.info(f"{'='*60}")

    # Initialize pipeline logger
    try:
        start_job(job_id, {
            'product_title': product_name,
            'product_image': product_image,
            'product_description': description,
            'recipe_name': recipe_name,
            'voice': voice,
            'ugc_style': ugc_style,
        })
    except Exception as e:
        logger.warning(f"Pipeline logger start failed: {e}")

    # ── Validate ugc_style from Schema Engine ──
    _orig_ugc = ugc_style
    ugc_style = validate_ugc_style(ugc_style)
    if ugc_style != _orig_ugc:
        logger.warning(f"  ugc_style '{_orig_ugc}' not valid, using '{ugc_style}'")

    pipeline_start = time.time()
    cost_image = 0.0
    cost_voice = 0.0
    cost_video = 0.0

    try:
        # ── STEP 1: Analyze ──
        step_start = time.time()
        product_profile = analyze_product(
            product_name, product_image, description, ugc_style=ugc_style,
            product_images=(product_images or []),
            gender=gender,
            target_age=age,
            body_part=kwargs.get("body_part", ""),
            special_target=kwargs.get("special_target", ""),
            usage_howto=kwargs.get("usage_howto", ""),
            ingredient_highlight=kwargs.get("ingredient_highlight", ""),
            category=kwargs.get("category", ""),
            subcategory=kwargs.get("subcategory", ""),
            duration=(duration if duration and duration > 0 else kwargs.get("duration", 15)),
            features=kwargs.get("features", "") or "",
        )

        # ── Wire prompt-builder (SSOT) outputs into pipeline args ──
        # The studio proxy (/api/v1/pipeline/full) sends NO pre-computed prompts,
        # and the legacy step6 builder lives in steps.disabled/ — so the prompts
        # from analyze_product() MUST be mapped here or Step 6/8 guards raise.
        # ("wire the prompt-builder output", never a hardcoded generic prompt.)
        if not video_prompts and not video_prompt:
            _vp = (product_profile or {}).get("_video_prompt") or ""
            if _vp:
                video_prompts = [_vp]
                logger.info(f"  Wired _video_prompt from prompt-builder ({len(_vp)} chars)")
        # 🔴 FIX 2026-09-10 (owner: "หลุด guard" from vid_179fcbda): the request may carry a
        # UI-supplied DEFAULT negative (frontend sends a 75-char generic text/watermark string
        # when the user leaves the field blank). That non-empty value used to short-circuit
        # `if not negative_prompt:` and DROP the superior Mimo-authored negative (~178ch with
        # distorted hands / extra fingers / warped product). Fix: the Mimo/prompt-builder
        # authored negative (product_profile["_negative_prompt"]) ALWAYS wins when present,
        # regardless of what the caller passed in.
        _authored_neg = (product_profile or {}).get("_negative_prompt") or ""
        if _authored_neg:
            if negative_prompt and negative_prompt.strip() != _authored_neg.strip():
                logger.info(
                    f"  🔁 override request negative_prompt ({len(negative_prompt)}ch) "
                    f"with authored Mimo/pb negative ({len(_authored_neg)}ch)"
                )
            negative_prompt = _authored_neg
        elif not negative_prompt:
            negative_prompt = _authored_neg
        analyze_duration = int((time.time() - step_start) * 1000)

        try:
            update_step(job_id, 'analyze', {'duration_ms': analyze_duration})
        except Exception:
            pass

        # ── STEP 2: Load Recipe ──
        step_start = time.time()
        recipe = load_recipe(recipe_name)
        recipe_duration = int((time.time() - step_start) * 1000)
        num_scenes = len(recipe.get("scenes", []))
        total_duration = duration if duration > 0 else recipe.get("total_duration", 8)

        try:
            update_step(job_id, 'recipe', {'duration_ms': recipe_duration, 'scenes': num_scenes})
        except Exception:
            pass

        # ── STEP 3: Generate Script (skip if pre-computed) ──
        if not script:
            step_start = time.time()
            # target_gender จาก product analyzer ชนะกว่า param (สินค้าผู้หญิง→female เสมอ)
            _gender = (product_profile or {}).get("target_gender") or gender
            script = generate_script(product_name, product_profile, recipe, ugc_style=ugc_style, gender=_gender)
            script_duration = int((time.time() - step_start) * 1000)
        else:
            script_duration = 0
            logger.info(f"Step 3/9: Skipped (using pre-computed script)")

        try:
            update_step(job_id, 'script', {'duration_ms': script_duration, 'script': script[:100]})
        except Exception:
            pass

        # ── VOICE MODE A ONLY (Gemini TTS removed from TUS — owner 2026-08-24) ──
        # Wan 2.7 พูด Thai script เองเสมอ: ถ้ามีบท (script/thai_script) →
        # auto ใช้บทนั้นเป็น thai_script + บังคับ use_tus_voice=True
        # ไม่มี Gemini TTS lip-sync แล้ว — เสียงในไฟล์จริงคือเสียงของ Wan เท่านั้น
        # 🔴 Owner 2026-09-02: งาน no-human ambient (indoor_projector/ambient_outdoor)
        # ไม่มีคนในคลิป → ห้ามฝังบทให้ Wan พูดเด็ดขาด (Wan จะสร้างปาก/พูดมั่ว ๆ แทรก
        # ทับคลิป เช่น vid_081ed2af พูด แอลอีดี ห้าสิบเมตร เพี้ยน) → ตัดบททิ้งเสมอ
        _nh_style = (ugc_style or "").strip().lower()
        if _nh_style in ("indoor_projector", "ambient_outdoor"):
            if thai_script or script:
                logger.warning(f"  No script for no-human style {_nh_style} — dropping thai_script/script (กัน Wan พูดมั่วแทรก)")
            thai_script = ""
            script = ""
        thai_script = (thai_script or script or "").strip()
        # 🔴 SAFETY NET (owner 2026-08-29): สุดท้ายก่อนฝังเข้า prompt ให้ Wan
        # ทับศัพท์ไทยล้วนเสมอ ไม่ว่าบทจะมาจากเส้นทางไหน (ลูกค้าส่งตรง / script_gen /
        # งานเก่า pre-computed) กันคำยากอังกฤษ (SPF50+ PA++++ 50g 30ml, Dr.PONG ฯลฯ)
        # หลุดเข้าบทที่ Wan พูด เพราะคำโรมันยาก ๆ Wan อ่านไม่ออกแล้วเพี้ยนช่วงท้าย
        if thai_script:
            try:
                from prompt_builder import _tts_product_name
                thai_script = _tts_product_name(thai_script) or thai_script
            except Exception as _e_safety:
                logger.warning(f"  ⚠ safety-net transliterate skipped: {_e_safety}")
        thai_script = thai_script.strip()
        # 🔴 Fix C: pull the timed beats for this job (if any) and apply the SAME transliteration
        # safety net to each spoken beat so the timeline text matches the flat thai_script.
        _beats_for_job = []
        try:
            _beats_for_job = list(product_profile.get("_script_beats") or [])
        except Exception:
            _beats_for_job = []
        if _beats_for_job and thai_script:
            try:
                from prompt_builder import _tts_product_name as _tts_pn
                _beats_for_job = [
                    {**b, "text": (_tts_pn(b.get("text") or "") or b.get("text") or "") if b.get("text") else ""}
                    for b in _beats_for_job
                ]
            except Exception as _e_beats:
                logger.warning(f"  ⚠ beats transliterate skipped: {_e_beats}")
        if thai_script and not use_tus_voice:
            # เจ้าสั่งให้ Wan พูด Thai script เสมอใน flow ปกติ → เปิดโหมด A อัตโนมัติ
            use_tus_voice = True
            logger.info(f"  🎙 Voice mode A: auto ใช้ script เป็น thai_script + เปิด use_tus_voice (Wan พูดเอง, ความยาว {len(thai_script)} ตัวอักษร)")
        if thai_script:
            # Verification aid (owner 2026-08-24): log the EXACT spoken lines
            logger.info(f"  🎙 thai_script spoken by Wan: {thai_script}")

        # ── STEP 4: Build Image Prompt (skip if pre-computed) ──
        if not image_prompt:
            step_start = time.time()
            image_prompt = build_image_prompt(product_name, product_profile, recipe)
            img_prompt_duration = int((time.time() - step_start) * 1000)
        else:
            img_prompt_duration = 0
            logger.info(f"Step 4/9: Skipped (using pre-computed image_prompt)")

        try:
            update_step(job_id, 'image_prompt', {'duration_ms': img_prompt_duration})
        except Exception:
            pass

        # ── STEP 5: Generate Image ──
        step_start = time.time()
        # owner 2026-09-14 (resume): when resuming a failed job we already have a still
        # image on disk - reuse it verbatim and SKIP nano-banana (do not burn image credit).
        _resume_img = kwargs.get("resume_image_path") or None
        if _resume_img:
            _rp = Path(_resume_img)
            if not _rp.exists():
                raise FileNotFoundError(
                    f"resume: image not found on disk: {_resume_img} (cannot resume)"
                )
            img_url = str(_rp)
            cost_image = 0.0
            img_path = _rp
            logger.info(f"Step 5/9: REUSING existing still (resume) — ${0.0:.4f} image cost, no nano-banana call: {img_path}")
        else:
            # Single 9:16 portrait (owner direction 2026-08-24).
            # Always portrait; do NOT switch to 16:9 landscape no matter what the
            # image_prompt text says.
            img_aspect = "9:16"
            # owner 2026-09-12: default placement = "place_and_hold" (product resting on the
            # surface with a hand reaching in) so the still frame is the "วางด้วย ถือด้วย" shot
            # the owner asked for. "holding"/"handheld" styles use place_and_hold; tabletop/demo
            # also place. Any other style falls back to hold.
            _plc_style = (ugc_style or "").strip().lower()
            # owner 2026-09-14 (fixes 'pants model still holding the jeans'): a WEARABLE garment must
            # NEVER get the hold/place_and_hold placement directive - those append a literal "holds the
            # product up" / "resting on a clean surface" clause that overrides the wear-style prompt and
            # re-introduces the held pose. Route wearables to the dedicated "wear" placement.
            _plc_name = ""
            try:
                _plc_name = (product_profile or {}).get("product_name") or product_name or ""
            except Exception:
                _plc_name = product_name or ""
            _plc_cat = (product_profile or {}).get("category") or kwargs.get("category", "") or ""
            _plc_sub = (product_profile or {}).get("subcategory") or kwargs.get("subcategory", "") or ""
            if is_wearable(category=_plc_cat, subcategory=_plc_sub, product_name=_plc_name):
                _placement = "wear"
                logger.info("  👕 wearable detected → placement=wear (no hold/place directive)")
            elif _plc_style in ("holding", "holding_demo", "handheld", "tabletop", "tabletop_demo", "demo", "review"):
                _placement = "place_and_hold"
            else:
                _placement = "hold"
            # owner 2026-09-12: when a multi-variant set was supplied and Mimo picked a reference
            # image (the one showing the most variants), use THAT as the img2img reference so the
            # still shows the full colour/flavour set instead of only image[0].
            _img_ref = product_image
            try:
                _ri = product_profile.get("_reference_image_index")
                _pimgs = [u for u in (product_images or []) if isinstance(u, str) and u.strip()]
                # owner 2026-09-12: Mimo's index refers to the ORIGINAL product_images order.
                # Determine the group-shot image (the one showing the most variants) and always use it
                # as the img2img anchor when available - this is what makes the still show the full
                # coloured line instead of a single repeated pack.
                _group_url = None
                if len(_pimgs) > 1:
                    try:
                        _gi = _pick_variant_reference_index(_pimgs)
                        if _gi is not None and 0 <= _gi < len(_pimgs):
                            _group_url = _pimgs[_gi]
                    except Exception:
                        pass
                if _group_url:
                    _img_ref = _group_url
                    logger.info(f"  🎨 reference image = group shot ({_group_url})")
                elif _ri is not None and _pimgs and 0 <= int(_ri) < len(_pimgs):
                    _img_ref = _pimgs[int(_ri)]
                    logger.info(f"  🎨 reference image from Mimo index {_ri}: {_img_ref}")
            except Exception as _e_ref:
                logger.warning(f"  reference image override skipped: {_e_ref}")
            img_url, cost_image = generate_image(
                image_prompt, _img_ref, aspect_ratio=img_aspect, placement=_placement
            )
            img_path = TMP_DIR / f"image_{run_id}.png"
            download_file(img_url, img_path)
        image_duration = int((time.time() - step_start) * 1000)

        try:
            update_step(job_id, 'image_gen', {'duration_ms': image_duration, 'output_path': str(img_path)})
            update_cost(job_id, 'image', cost_image)
        except Exception:
            pass

        # ── STEP 6: Build Video Prompts (skip if pre-computed) ──
        if not video_prompts and video_prompt:
            video_prompts = [video_prompt]
            vid_prompt_duration = 0
            logger.info(f"Step 6/9: Skipped (using pre-computed video_prompt)")
        elif not video_prompts:
            # NO hardcoded generic prompt. This exact fallback is what produced
            # the "speaks Vietnamese/gibberish" raw video (a generic English prompt
            # with no Thai script went to Wan). Prompts MUST come from the
            # JSON-driven prompt-builder — break loudly instead of regressing.
            # (docs-exact 2026-08-15: ห้ามฝัง script ลง prompt — ไปอยู่ TTS อย่างเดียว)
            raise ValueError(
                "pipeline: video_prompts missing and no video_prompt supplied — "
                "refusing hardcoded generic prompt; wire the prompt-builder output"
            )
        else:
            vid_prompt_duration = 0
            logger.info(f"Step 6/9: Skipped (using pre-computed video_prompts)")

        try:
            update_step(job_id, 'video_prompts', {'duration_ms': vid_prompt_duration, 'count': len(video_prompts)})
        except Exception:
            pass

        # Save all prompts + script to logger
        try:
            update_prompts(job_id, {
                'image_prompt': image_prompt,
                'video_prompts': video_prompts,
                'script': script,
                'negative_prompt': negative_prompt if negative_prompt else '',
                'hashtags': product_profile.get('hashtags', []),
            })
        except Exception as e:
            logger.warning(f"Logger update_prompts failed: {e}")

        # ── STEP 7: REMOVED (Gemini TTS stripped from TUS — owner 2026-08-24) ──
        voice_path = None
        cost_voice = 0.0
        logger.info("Step 7/9: REMOVED — Gemini TTS ถูกถอดออกจาก TUS (Wan พูด thai_script เอง)")

        # ── STEP 8: Generate 1 Video (Wan 2.7 Sync, 1 clip full duration) ──
        # WHY 1 clip: Wan 2.7 img2vid generates from a SINGLE image reference.
        # Multiple independent clips from the same static image = jarring cuts,
        # same product angle every scene, zero visual continuity.
        # 1 continuous generation = smooth motion, natural flow.
        step_start = time.time()
        video_paths = []
        
        vprompt = video_prompts[0] if video_prompts else ""
        if not vprompt:
            # No hardcoded video prompt — raise clearly. Prompts must come from
            # prompt-builder (JSON-driven). Breaking loudly beats a silent generic
            # fallback that diverges from the JSON prompt sources.
            raise ValueError("pipeline: video_prompts is empty/None — no prompt to generate video; refusing hardcoded fallback")
        logger.info(f"  Generating 1 continuous video ({total_duration}s): {vprompt[:80]}...")

        # ── Start/End frames (SINGLE image — owner 2026-08-26) ──
        # Owner direction: FL2V ใช้รูปเดียวคือรูปแรก (first frame) — ห้าม start-end
        # interpolation, ห้าม gen last frame (klein end-scene). เหตุผล: interpolation
        # ทำให้ตอนท้ายวิดีโอสินค้า/องค์ประกอบเพี้ยนไปจากต้น (พี่เจอ "ตอนท้ายผิด").
        # ff = first frame (Nano Banana img2img 9:16 gen จาก reference)
        # lf = ไม่ใช้ — single image เสมอ
        ff = first_frame or str(img_path)
        lf = None
        logger.info(f"  ▶ FL2V SINGLE image (owner rule 2026-08-26): first=({Path(ff).name}), last=None (no klein, no start-end)")

        # Gemini TTS removed from TUS (owner 2026-08-24): no lip-sync audio.
        logger.info("  🎙 SP8: Wan พูดเอง (Voice mode A เท่านั้น)")
        vid_path, cost_video = generate_video(
            image_path=str(img_path),
            prompt=vprompt,
            # 💬 REMARK 2026-08-24: duration รับได้แค่ [8, 15] เท่านั้น (ALLOWED_DURATIONS ใน config.py)
            # — อย่าส่ง 5/อื่นนอกจาก 8,15 → validator VideoRequest reject ทันที (ไม่เกี่ยวกับ Wan)
            # FIX 2026-08-25 (owner bug vid_2d9f4395): ใช้ total_duration จาก request
            # เดิม hardcode duration=8 (commit 48988d52) → user เลือก 15s ใน web UI
            # แต่ Wan gen แค่ 8s แล้ว compose stream_loop ยืดเป็น 15s = เสียง+ภาพวนซ้ำ
            duration=total_duration,
            negative_prompt=negative_prompt,
            # FL2V SINGLE image (owner 2026-08-26): ส่ง first frame รูปเดียว
            # ไม่มี last_frame ไม่มี reference (ห้ามส่ง reference แยก — Prodia จะเอาเป็นภาพหลัก)
            reference_image=None,
            first_frame=ff,
            last_frame=None,
            thai_script=thai_script,
            use_tus_voice=use_tus_voice,
            prompt_extend=prompt_extend,
            ugc_style=ugc_style,
            script_beats=_beats_for_job,
        )
        video_paths.append(vid_path)
        
        video_gen_duration = int((time.time() - step_start) * 1000)

        try:
            update_step(job_id, 'video_gen', {
                'duration_ms': video_gen_duration,
                'output_path': video_paths[-1] if video_paths else ''
            })
            update_cost(job_id, 'video', cost_video)
        except Exception:
            pass

        # ── STEP 9: Compose ──
        # Duration target: ใช้ค่า `total_duration` (ที่ user/request ระบุ เช่น 15s) เป็นเป้า
        # เสมอ — ถ้า Prodia Wan กลับมาสั้นกว่า (Wan 2.7 ทำได้ ~8s แม้ขอ 15s) ให้ 9a.5
        # -stream_loop ยืดให้เต็ม target (owner อยากได้ 15 วิ เพิ่มจาก 8 วิ)
        # เดิม forced ใช้ actual_video_duration → 15s job กลายเป็น 8s ไม่ง่าย target
        target_duration = total_duration if total_duration > 0 else recipe.get("total_duration", 0)
        final_duration = target_duration if target_duration > 0 else 0
        # Gemini TTS removed from TUS (owner 2026-08-24): compose mixes BGM
        # over Wan's own audio only — never a TTS voiceover.
        final_path, raw_path = compose_video(video_paths, None, run_id, bgm_style, target_duration=final_duration)

        # Preserve the TRUE Prodia output (before any compose/edit) permanently.
        # raw_path = affiliate_{run_id}_raw.mp4 is a POST-compose concat output.
        # The raw Wan 2.7 Prodia file is vid_path (img2vid_*.mp4) — copy it out of
        # TMP (which gets cleaned) so the UI "ไฟล์ที่สร้าง" can show what Prodia
        # actually generated, letting the user see the un-edited lip-sync source.
        prodia_src = vid_path if vid_path else (video_paths[-1] if video_paths else '')
        prodia_raw_path = ''
        if prodia_src and os.path.exists(prodia_src):
            prodia_raw_path = str(STORAGE_DIR / f"raw_prodia_{run_id}.mp4")
            shutil.copy2(prodia_src, prodia_raw_path)
            logger.info(f"  Prodia raw preserved -> {prodia_raw_path}")

        # Cost summary
        cost_total = cost_image + cost_voice + cost_video
        total_duration_ms = int((time.time() - pipeline_start) * 1000)

        logger.info(f"{'='*60}")
        logger.info(f"Pipeline v6 complete: {final_path}")
        logger.info(f"Cost: ${cost_total:.4f}")
        logger.info(f"Time: {total_duration_ms/1000:.1f}s")
        logger.info(f"{'='*60}")

        # Log completion — raw_video_path now points at the true Prodia output
        # (raw_prodia_{run_id}.mp4). The compose-concat output (raw_path) stays
        # on disk for reference but is no longer exposed as "Raw Video".
        try:
            complete_job(
                job_id,
                final_path=str(final_path),
                total_duration_ms=total_duration_ms,
                total_video_duration=total_duration,
                total_scenes=num_scenes,
                raw_video_path=prodia_raw_path or str(raw_path)
            )
        except Exception as e:
            logger.warning(f"Pipeline logger complete failed: {e}")

        return {
            "run_id": run_id,
            "final_path": str(final_path),
            "duration": total_duration,
            "cost_estimate": round(cost_total, 4),
            "cost_breakdown": {
                "image": round(cost_image, 4),
                "voice": round(cost_voice, 4),
                "video": round(cost_video, 4),
                "total": round(cost_total, 4),
            },
            "product_profile": {k: v for k, v in product_profile.items() if not k.startswith("_")},
            "hashtags": product_profile.get('hashtags', []),
            "recipe": recipe_name,
            "script": script,
            "image_path": str(img_path),
            "video_paths": video_paths,
            "job_id": job_id,
        }

    except Exception as e:
        try:
            fail_job(job_id, str(e), 'unknown')
        except Exception as e2:
            logger.warning(f"Pipeline logger fail failed: {e2}")
        raise



# ═══════════════════════════════════════════════════════════════════════════
# RESUME: re-run a FAILED job from its existing still image (owner 2026-09-14)
# ═══════════════════════════════════════════════════════════════════════════
def resume_pipeline(job_id: str, **overrides) -> dict:
    """Resume a FAILED pipeline job WITHOUT regenerating the still image.

    WHY: Prodia Wan 2.7 flakily fails ("unknown error"). The still image (nano-banana)
    and the analysis/script/prompts are already produced and PAID FOR by the time the
    video step fails. This re-runs only video + compose against the SAME still, so no
    image credit is wasted.

    Reads the failed job's stored fields (image_path, video_prompts, script, negative,
    duration, aspect, ugc_style) from pipeline_logs.db and calls run_pipeline() with
    resume_image_path set so Step 5 is skipped.

    Raises ValueError if the job is missing, not failed, has no still image, or the
    image file no longer exists on disk.
    """
    job = get_job(job_id)
    if not job:
        raise ValueError(f"resume: job not found: {job_id}")

    status = (job.get("status") or "").lower()
    if status == "completed":
        raise ValueError(f"resume: job {job_id} is already completed — nothing to resume")
    if status not in ("failed", "error", ""):
        raise ValueError(f"resume: job {job_id} status='{status}' is not resumable (expected failed)")

    img = job.get("generated_image_path") or ""
    if not img:
        raise ValueError(f"resume: job {job_id} has no generated_image_path — cannot resume")
    img_p = Path(img)
    if not img_p.exists():
        raise ValueError(f"resume: still image missing on disk: {img} — cannot resume")

    # video_prompts is stored as a JSON string.
    vps_raw = job.get("video_prompts") or ""
    video_prompts = None
    if vps_raw:
        try:
            parsed = json.loads(vps_raw) if isinstance(vps_raw, str) else vps_raw
            if isinstance(parsed, list) and parsed:
                video_prompts = [str(x) for x in parsed if x]
        except Exception:
            logger.warning(f"  resume: could not parse stored video_prompts; will re-derive")

    dur = job.get("total_duration_seconds") or 0
    try:
        dur = int(float(dur)) if dur else 15
    except Exception:
        dur = 15
    if dur not in (8, 15):
        dur = 15

    logger.info(f"{'='*60}")
    logger.info(f"RESUME job {job_id} — reusing still {img} (NO image regen)")
    logger.info(f"{'='*60}")

    _bgm = overrides.pop("bgm_style", None) or "chill_loft"
    kwargs = dict(
        product_name=job.get("product_title") or "สินค้า",
        product_image=job.get("product_image_path") or "",
        description=job.get("product_description") or "",
        recipe_name=job.get("recipe_name") or "tus",
        voice=job.get("voice") or "Aoede",
        bgm_style=_bgm,
        ugc_style=job.get("ugc_style") or "holding",
        external_job_id=job_id,
        duration=dur,
        image_prompt=job.get("image_prompt") or "",
        video_prompts=video_prompts or [],
        negative_prompt=job.get("negative_prompt") or "",
        script=job.get("script") or "",
        resume_image_path=img,
    )
    kwargs.update(overrides)
    return run_pipeline(**kwargs)
