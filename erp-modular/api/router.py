"""FastAPI CRUD Router สำหรับ Module/Template/Entity/Plugin/App"""

from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List

from models.entity import (
    Module, ModuleCreate, ModuleRead,
    Template, TemplateCreate, TemplateRead,
    Entity, EntityCreate, EntityRead,
    Plugin, PluginCreate, PluginRead,
    App, AppCreate, AppRead,
)
from core.database import get_session

router = APIRouter(prefix="/api/v1")


# ─── Module CRUD ─────────────────────────────────────────────────────────

@router.post("/modules", response_model=ModuleRead)
def create_module(module: ModuleCreate, session: Session = Depends(get_session)):
    db_module = Module(**module.model_dump())
    session.add(db_module)
    session.commit()
    session.refresh(db_module)
    return db_module


@router.get("/modules", response_model=List[ModuleRead])
def list_modules(session: Session = Depends(get_session)):
    return session.exec(select(Module)).all()


@router.get("/modules/{module_id}", response_model=ModuleRead)
def get_module(module_id: int, session: Session = Depends(get_session)):
    module = session.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module


@router.delete("/modules/{module_id}")
def delete_module(module_id: int, session: Session = Depends(get_session)):
    module = session.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    session.delete(module)
    session.commit()
    return {"ok": True}


# ─── Template CRUD ───────────────────────────────────────────────────────

@router.post("/templates", response_model=TemplateRead)
def create_template(template: TemplateCreate, session: Session = Depends(get_session)):
    db_template = Template(**template.model_dump())
    session.add(db_template)
    session.commit()
    session.refresh(db_template)
    return db_template


@router.get("/templates", response_model=List[TemplateRead])
def list_templates(session: Session = Depends(get_session)):
    return session.exec(select(Template)).all()


@router.get("/templates/{template_id}", response_model=TemplateRead)
def get_template(template_id: int, session: Session = Depends(get_session)):
    template = session.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


# ─── Entity CRUD ─────────────────────────────────────────────────────────

@router.post("/entities", response_model=EntityRead)
def create_entity(entity: EntityCreate, session: Session = Depends(get_session)):
    db_entity = Entity(**entity.model_dump())
    session.add(db_entity)
    session.commit()
    session.refresh(db_entity)
    return db_entity


@router.get("/entities", response_model=List[EntityRead])
def list_entities(session: Session = Depends(get_session)):
    return session.exec(select(Entity)).all()


@router.get("/entities/{entity_id}", response_model=EntityRead)
def get_entity(entity_id: int, session: Session = Depends(get_session)):
    entity = session.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


# ─── Plugin CRUD ─────────────────────────────────────────────────────────

@router.post("/plugins", response_model=PluginRead)
def create_plugin(plugin: PluginCreate, session: Session = Depends(get_session)):
    db_plugin = Plugin(**plugin.model_dump())
    session.add(db_plugin)
    session.commit()
    session.refresh(db_plugin)
    return db_plugin


@router.get("/plugins", response_model=List[PluginRead])
def list_plugins(session: Session = Depends(get_session)):
    return session.exec(select(Plugin)).all()


@router.get("/plugins/{plugin_id}", response_model=PluginRead)
def get_plugin(plugin_id: int, session: Session = Depends(get_session)):
    plugin = session.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return plugin


# ─── App CRUD ────────────────────────────────────────────────────────────

@router.post("/apps", response_model=AppRead)
def create_app(app: AppCreate, session: Session = Depends(get_session)):
    db_app = App(**app.model_dump())
    session.add(db_app)
    session.commit()
    session.refresh(db_app)
    return db_app


@router.get("/apps", response_model=List[AppRead])
def list_apps(session: Session = Depends(get_session)):
    return session.exec(select(App)).all()


@router.get("/apps/{app_id}", response_model=AppRead)
def get_app(app_id: int, session: Session = Depends(get_session)):
    app = session.get(App, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return app
