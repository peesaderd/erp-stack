"""FastAPI CRUD Router สำหรับ Module/Template/Entity/Plugin/App

มี endpoints:
- POST/GET list/GET by id/PUT/PATCH/DELETE สำหรับทุก entity
- search query parameter สำหรับ list endpoints
- Template Engine: render template
- Plugin Registry: install/activate/deactivate/uninstall
- Auth: JWT + RBAC (optional — ใช้ require_auth เมื่อต้องการ)
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlmodel import Session, select, func
from typing import List, Optional, Any

from models.entity import (
    Module, ModuleCreate, ModuleUpdate, ModuleRead,
    Template, TemplateCreate, TemplateUpdate, TemplateRead,
    Entity, EntityCreate, EntityUpdate, EntityRead,
    Plugin, PluginCreate, PluginUpdate, PluginRead,
    App, AppCreate, AppUpdate, AppRead,
)
from core.database import get_session
from core.template_engine import TemplateEngine
from .auth import TokenData, require_auth, require_permission, require_role, PERM_ADMIN

router = APIRouter(prefix="/api/v1")

# ─── Template Engine instance ─────────────────────────────────────────────
_template_engine = None


def _get_db_session():
    """เรียกใช้จริง: next(get_session()) เพื่อให้ได้ Session object"""
    return next(get_session())


def get_template_engine():
    global _template_engine
    if _template_engine is None:
        _template_engine = TemplateEngine(_get_db_session, template_dirs=["templates"])
    return _template_engine


# ─── Helper ──────────────────────────────────────────────────────────────

def _apply_search(stmt, model, search: Optional[str]):
    """เพิ่มเงื่อนไข search ใน query — ค้นหาจาก name, slug, description"""
    if not search:
        return stmt
    pattern = f"%{search}%"
    return stmt.where(
        model.name.ilike(pattern)
        | model.slug.ilike(pattern)
        | model.description.ilike(pattern)
    )


def _patch_model(db_obj, update_data: dict):
    """อัปเดตเฉพาะ field ที่ส่งมา (ไม่ใช่ None)"""
    for key, val in update_data.items():
        if val is not None:
            setattr(db_obj, key, val)


# ═══════════════════════════════════════════════════════════════════════════
# Module CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/modules", response_model=ModuleRead)
def create_module(module: ModuleCreate, session: Session = Depends(get_session)):
    db_module = Module(**module.model_dump())
    session.add(db_module)
    session.commit()
    session.refresh(db_module)
    return db_module


@router.post("/modules/register", response_model=ModuleRead)
def register_module(
    data: dict = Body(...),
    session: Session = Depends(get_session),
):
    """Register a live module from erp_bridge — creates or updates Module record."""
    name = data.get("name", data.get("slug", "unknown"))
    slug = data.get("slug", name.lower().replace(" ", "-"))
    endpoint = data.get("endpoint", "")
    description = data.get("description", "")
    version = data.get("version", "1.0.0")

    existing = session.exec(select(Module).where(Module.slug == slug)).first()
    if existing:
        existing.name = name
        existing.description = description or existing.description
        existing.version = version
        session.commit()
        session.refresh(existing)
        return existing

    db_module = Module(
        name=name,
        slug=slug,
        description=description,
        version=version,
    )
    session.add(db_module)
    session.commit()
    session.refresh(db_module)
    return db_module


@router.get("/modules", response_model=List[ModuleRead])
def list_modules(
    search: Optional[str] = Query(None, description="ค้นหาจาก name, slug, description"),
    enabled: Optional[bool] = Query(None, description="กรองตามสถานะ"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    stmt = select(Module)
    stmt = _apply_search(stmt, Module, search)
    if enabled is not None:
        stmt = stmt.where(Module.enabled == enabled)
    stmt = stmt.offset(skip).limit(limit)
    return session.exec(stmt).all()


@router.get("/modules/{module_id}", response_model=ModuleRead)
def get_module(module_id: int, session: Session = Depends(get_session)):
    module = session.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module


@router.put("/modules/{module_id}", response_model=ModuleRead)
def update_module(module_id: int, data: ModuleUpdate, session: Session = Depends(get_session)):
    module = session.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    _patch_model(module, data.model_dump())
    session.commit()
    session.refresh(module)
    return module


@router.delete("/modules/{module_id}")
def delete_module(module_id: int, session: Session = Depends(get_session)):
    module = session.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    session.delete(module)
    session.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# Template CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/templates", response_model=TemplateRead)
def create_template(template: TemplateCreate, session: Session = Depends(get_session)):
    db_template = Template(**template.model_dump())
    session.add(db_template)
    session.commit()
    session.refresh(db_template)
    return db_template


@router.get("/templates", response_model=List[TemplateRead])
def list_templates(
    search: Optional[str] = Query(None, description="ค้นหาจาก name, slug, description"),
    template_type: Optional[str] = Query(None, description="กรองตามประเภท (entity/module/plugin)"),
    module_id: Optional[int] = Query(None, description="กรองตาม module"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    stmt = select(Template)
    stmt = _apply_search(stmt, Template, search)
    if template_type:
        stmt = stmt.where(Template.template_type == template_type)
    if module_id is not None:
        stmt = stmt.where(Template.module_id == module_id)
    stmt = stmt.offset(skip).limit(limit)
    return session.exec(stmt).all()


@router.get("/templates/{template_id}", response_model=TemplateRead)
def get_template(template_id: int, session: Session = Depends(get_session)):
    template = session.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/templates/{template_id}", response_model=TemplateRead)
def update_template(template_id: int, data: TemplateUpdate, session: Session = Depends(get_session)):
    template = session.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    _patch_model(template, data.model_dump())
    session.commit()
    session.refresh(template)
    return template


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, session: Session = Depends(get_session)):
    template = session.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    session.delete(template)
    session.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# Entity CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/entities", response_model=EntityRead)
def create_entity(entity: EntityCreate, session: Session = Depends(get_session)):
    db_entity = Entity(**entity.model_dump())
    session.add(db_entity)
    session.commit()
    session.refresh(db_entity)
    return db_entity


@router.get("/entities", response_model=List[EntityRead])
def list_entities(
    search: Optional[str] = Query(None, description="ค้นหาจาก name, slug, description"),
    module_id: Optional[int] = Query(None, description="กรองตาม module"),
    tag: Optional[str] = Query(None, description="กรองตาม tag (ค้นหาใน tags field)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    stmt = select(Entity)
    stmt = _apply_search(stmt, Entity, search)
    if module_id is not None:
        stmt = stmt.where(Entity.module_id == module_id)
    if tag:
        stmt = stmt.where(Entity.tags.ilike(f"%{tag}%"))
    stmt = stmt.offset(skip).limit(limit)
    return session.exec(stmt).all()


@router.get("/entities/{entity_id}", response_model=EntityRead)
def get_entity(entity_id: int, session: Session = Depends(get_session)):
    entity = session.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.put("/entities/{entity_id}", response_model=EntityRead)
def update_entity(entity_id: int, data: EntityUpdate, session: Session = Depends(get_session)):
    entity = session.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    _patch_model(entity, data.model_dump())
    session.commit()
    session.refresh(entity)
    return entity


@router.delete("/entities/{entity_id}")
def delete_entity(entity_id: int, session: Session = Depends(get_session)):
    entity = session.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    session.delete(entity)
    session.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# Plugin CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/plugins", response_model=PluginRead)
def create_plugin(plugin: PluginCreate, session: Session = Depends(get_session)):
    db_plugin = Plugin(**plugin.model_dump())
    session.add(db_plugin)
    session.commit()
    session.refresh(db_plugin)
    return db_plugin


@router.get("/plugins", response_model=List[PluginRead])
def list_plugins(
    search: Optional[str] = Query(None, description="ค้นหาจาก name, slug, description"),
    enabled: Optional[bool] = Query(None, description="กรองตามสถานะ"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    stmt = select(Plugin)
    stmt = _apply_search(stmt, Plugin, search)
    if enabled is not None:
        stmt = stmt.where(Plugin.enabled == enabled)
    stmt = stmt.offset(skip).limit(limit)
    return session.exec(stmt).all()


@router.get("/plugins/{plugin_id}", response_model=PluginRead)
def get_plugin(plugin_id: int, session: Session = Depends(get_session)):
    plugin = session.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return plugin


@router.put("/plugins/{plugin_id}", response_model=PluginRead)
def update_plugin(plugin_id: int, data: PluginUpdate, session: Session = Depends(get_session)):
    plugin = session.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    _patch_model(plugin, data.model_dump())
    session.commit()
    session.refresh(plugin)
    return plugin


@router.delete("/plugins/{plugin_id}")
def delete_plugin(plugin_id: int, session: Session = Depends(get_session)):
    plugin = session.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    session.delete(plugin)
    session.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# App CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/apps", response_model=AppRead)
def create_app(app: AppCreate, session: Session = Depends(get_session)):
    db_app = App(**app.model_dump())
    session.add(db_app)
    session.commit()
    session.refresh(db_app)
    return db_app


@router.get("/apps", response_model=List[AppRead])
def list_apps(
    search: Optional[str] = Query(None, description="ค้นหาจาก name, slug, description"),
    enabled: Optional[bool] = Query(None, description="กรองตามสถานะ"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    stmt = select(App)
    stmt = _apply_search(stmt, App, search)
    if enabled is not None:
        stmt = stmt.where(App.enabled == enabled)
    stmt = stmt.offset(skip).limit(limit)
    return session.exec(stmt).all()


@router.get("/apps/{app_id}", response_model=AppRead)
def get_app(app_id: int, session: Session = Depends(get_session)):
    app = session.get(App, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return app


@router.put("/apps/{app_id}", response_model=AppRead)
def update_app(app_id: int, data: AppUpdate, session: Session = Depends(get_session)):
    app = session.get(App, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    _patch_model(app, data.model_dump())
    session.commit()
    session.refresh(app)
    return app


@router.delete("/apps/{app_id}")
def delete_app(app_id: int, session: Session = Depends(get_session)):
    app = session.get(App, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    session.delete(app)
    session.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# Template Engine
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/templates/render", response_model=dict)
def render_template(
    template_slug: str = Body(..., description="slug หรือ name ของ template"),
    context: dict = Body(default_factory=dict, description="ข้อมูลที่จะส่งเข้า template"),
    engine: TemplateEngine = Depends(get_template_engine),
):
    """Render template ที่บันทึกใน DB ด้วย context ที่ส่งเข้าไป"""
    try:
        result = engine.render(template_slug, context)
        return {"template": template_slug, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/templates/render-inline", response_model=dict)
def render_inline_template(
    content: str = Body(..., description="template content (Jinja2 string)"),
    context: dict = Body(default_factory=dict, description="ข้อมูลที่จะส่งเข้า template"),
    engine: TemplateEngine = Depends(get_template_engine),
):
    """Render template จาก string โดยตรง (ไม่ได้บันทึกใน DB)"""
    try:
        result = engine.render_from_content(content, context)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/templates/{template_id}/render", response_model=dict)
def render_template_by_id(
    template_id: int,
    context: dict = Body(default_factory=dict, description="ข้อมูลที่จะส่งเข้า template"),
    session: Session = Depends(get_session),
    engine: TemplateEngine = Depends(get_template_engine),
):
    """Render template ตาม ID"""
    tmpl = session.get(Template, template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        result = engine.render(tmpl.slug, context)
        return {"template": tmpl.slug, "name": tmpl.name, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# Plugin Registry — Lifecycle Management
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/plugins/{plugin_id}/install", response_model=PluginRead)
def install_plugin(plugin_id: int, session: Session = Depends(get_session)):
    """ติดตั้ง Plugin: โหลดโมดูล, เรียก install hook, set enabled=True"""
    plugin = session.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    if plugin.enabled:
        raise HTTPException(status_code=400, detail="Plugin already installed")

    # ตรวจสอบ dependencies
    if plugin.dependencies:
        dep_slugs = [s.strip() for s in plugin.dependencies.split(",") if s.strip()]
        for dep_slug in dep_slugs:
            dep = session.exec(
                select(Plugin).where(Plugin.slug == dep_slug, Plugin.enabled == True)
            ).first()
            if not dep:
                raise HTTPException(
                    status_code=400,
                    detail=f"Dependency '{dep_slug}' not found or not enabled. "
                           f"กรุณาติดตั้ง {dep_slug} ก่อน",
                )

    # พยายามโหลดโมดูล plugin
    try:
        module_path = f"plugins.{plugin.slug}.main"
        import importlib
        mod = importlib.import_module(module_path)
        if hasattr(mod, "install"):
            mod.install()
    except ModuleNotFoundError:
        # ไม่มีโมดูลจริง — อนุญาตให้ผ่าน (สำหรับ registered plugins ที่ยังไม่มี code)
        pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plugin install error: {str(e)}")

    plugin.enabled = True
    session.commit()
    session.refresh(plugin)
    return plugin


@router.post("/plugins/{plugin_id}/activate", response_model=PluginRead)
def activate_plugin(plugin_id: int, session: Session = Depends(get_session)):
    """เปิดใช้งาน Plugin: เรียก activate hook"""
    plugin = session.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    if not plugin.enabled:
        raise HTTPException(status_code=400, detail="Plugin not installed. กรุณา install ก่อน")

    try:
        module_path = f"plugins.{plugin.slug}.main"
        import importlib
        mod = importlib.import_module(module_path)
        if hasattr(mod, "activate"):
            mod.activate()
    except ModuleNotFoundError:
        pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plugin activate error: {str(e)}")

    return plugin


@router.post("/plugins/{plugin_id}/deactivate", response_model=PluginRead)
def deactivate_plugin(plugin_id: int, session: Session = Depends(get_session)):
    """ปิดใช้งาน Plugin: เรียก deactivate hook"""
    plugin = session.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    try:
        module_path = f"plugins.{plugin.slug}.main"
        import importlib
        mod = importlib.import_module(module_path)
        if hasattr(mod, "deactivate"):
            mod.deactivate()
    except ModuleNotFoundError:
        pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plugin deactivate error: {str(e)}")

    return plugin


@router.post("/plugins/{plugin_id}/uninstall", response_model=PluginRead)
def uninstall_plugin(plugin_id: int, session: Session = Depends(get_session)):
    """ถอนการติดตั้ง Plugin: เรียก uninstall hook, set enabled=False"""
    plugin = session.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    try:
        module_path = f"plugins.{plugin.slug}.main"
        import importlib
        mod = importlib.import_module(module_path)
        if hasattr(mod, "uninstall"):
            mod.uninstall()
    except ModuleNotFoundError:
        pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plugin uninstall error: {str(e)}")

    plugin.enabled = False
    session.commit()
    session.refresh(plugin)
    return plugin


@router.post("/plugins/{plugin_id}/execute", response_model=dict)
def execute_plugin(
    plugin_id: int,
    params: dict = Body(default_factory=dict, description="parameters ส่งให้ plugin execute"),
    session: Session = Depends(get_session),
):
    """Execute Plugin: เรียก execute hook พร้อม parameters"""
    plugin = session.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    if not plugin.enabled:
        raise HTTPException(status_code=400, detail="Plugin not installed. กรุณา install ก่อน")

    try:
        module_path = f"plugins.{plugin.slug}.main"
        import importlib
        mod = importlib.import_module(module_path)
        if hasattr(mod, "execute"):
            result = mod.execute(**params)
            return {"plugin": plugin.slug, "result": result}
        else:
            raise HTTPException(status_code=400, detail="Plugin has no execute() function")
    except ModuleNotFoundError:
        raise HTTPException(
            status_code=400,
            detail=f"Plugin module 'plugins.{plugin.slug}.main' not found. "
                   f"กรุณาสร้างไฟล์ plugins/{plugin.slug}/main.py",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plugin execute error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/stats")
def get_stats(session: Session = Depends(get_session)):
    """ดูสถิติของระบบ — จำนวน entity แต่ละประเภท"""
    return {
        "modules": session.exec(select(func.count(Module.id))).one(),
        "templates": session.exec(select(func.count(Template.id))).one(),
        "entities": session.exec(select(func.count(Entity.id))).one(),
        "plugins": session.exec(select(func.count(Plugin.id))).one(),
        "apps": session.exec(select(func.count(App.id))).one(),
    }
