"""Core Data Models for ERP Modular - Pydantic v2 + SQLModel

Entities:
- Module: กลุ่มของ Entity ที่ทำงานร่วมกัน (Accounting, CRM, Inventory)
- Template: แม่แบบสำหรับสร้าง Entity หรือ Module ซ้ำ
- Entity: สิ่งของในระบบ (Customer, Invoice, Product, Order)
- Plugin: ส่วนขยายที่แทรกเข้าไปในระบบได้
- App: Mini App ที่เชื่อมต่อผ่าน API Gateway
"""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, Column, JSON
from pydantic import BaseModel, field_validator


# ─── Base ────────────────────────────────────────────────────────────────

class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)})


# ─── Entity ──────────────────────────────────────────────────────────────

# ─── Validators ──────────────────────────────────────────────────────────

def _validate_slug(v: str) -> str:
    """slug ต้องเป็น lowercase, ไม่มี space, ใช้ - คั่น"""
    if not v or not v.strip():
        raise ValueError("slug ห้ามว่าง")
    v = v.strip().lower().replace(" ", "-")
    if not all(c.isalnum() or c == "-" or c == "_" for c in v):
        raise ValueError("slug ใช้ได้เฉพาะ a-z, 0-9, -, _")
    return v


# ─── Entity ──────────────────────────────────────────────────────────────

class EntityBase(SQLModel):
    """สิ่งของในระบบ เช่น Customer, Invoice, Product, Order"""
    name: str = Field(min_length=1, max_length=200, index=True)
    slug: str = Field(min_length=1, max_length=200, unique=True, index=True)
    description: Optional[str] = Field(default=None, max_length=2000)
    module_id: Optional[int] = Field(default=None, foreign_key="module.id")
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    tags: Optional[str] = Field(default=None, max_length=500, description="tags คั่นด้วย comma")


class Entity(EntityBase, TimestampMixin, table=True):
    __tablename__ = "entity"
    id: Optional[int] = Field(default=None, primary_key=True)


class EntityCreate(EntityBase):
    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        return _validate_slug(v)


class EntityUpdate(BaseModel):
    """สำหรับ update — ทุก field เป็น optional"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    module_id: Optional[int] = None
    config: Optional[dict] = None
    tags: Optional[str] = Field(default=None, max_length=500)


class EntityRead(EntityBase):
    id: int
    created_at: datetime
    updated_at: datetime


# ─── Module ──────────────────────────────────────────────────────────────

class ModuleBase(SQLModel):
    """กลุ่มของ Entity ที่ทำงานร่วมกัน เช่น Accounting, CRM, Inventory"""
    name: str = Field(min_length=1, max_length=200, index=True)
    slug: str = Field(min_length=1, max_length=200, unique=True, index=True)
    description: Optional[str] = Field(default=None, max_length=2000)
    version: str = Field(default="0.1.0", max_length=20)
    enabled: bool = Field(default=True)
    icon: Optional[str] = Field(default=None, max_length=50, description="icon name (emoji หรือ Material Icon)")
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Module(ModuleBase, TimestampMixin, table=True):
    __tablename__ = "module"
    id: Optional[int] = Field(default=None, primary_key=True)


class ModuleCreate(ModuleBase):
    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        return _validate_slug(v)


class ModuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    version: Optional[str] = Field(default=None, max_length=20)
    enabled: Optional[bool] = None
    icon: Optional[str] = Field(default=None, max_length=50)
    config: Optional[dict] = None


class ModuleRead(ModuleBase):
    id: int
    created_at: datetime
    updated_at: datetime


# ─── Template ────────────────────────────────────────────────────────────

class TemplateBase(SQLModel):
    """แม่แบบสำหรับสร้าง Entity หรือ Module ซ้ำ"""
    name: str = Field(min_length=1, max_length=200, index=True)
    slug: str = Field(min_length=1, max_length=200, unique=True, index=True)
    description: Optional[str] = Field(default=None, max_length=2000)
    template_type: str = Field(default="entity", max_length=20)  # "entity" | "module" | "plugin"
    schema_def: dict = Field(default_factory=dict, sa_column=Column(JSON))
    module_id: Optional[int] = Field(default=None, foreign_key="module.id")


class Template(TemplateBase, TimestampMixin, table=True):
    __tablename__ = "template"
    id: Optional[int] = Field(default=None, primary_key=True)


class TemplateCreate(TemplateBase):
    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        return _validate_slug(v)

    @field_validator("template_type")
    @classmethod
    def validate_type(cls, v):
        allowed = {"entity", "module", "plugin"}
        if v not in allowed:
            raise ValueError(f"template_type ต้องเป็น {allowed}")
        return v


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    template_type: Optional[str] = Field(default=None, max_length=20)
    schema_def: Optional[dict] = None
    module_id: Optional[int] = None


class TemplateRead(TemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime


# ─── Plugin ──────────────────────────────────────────────────────────────

class PluginBase(SQLModel):
    """ส่วนขยายที่แทรกเข้าไปในระบบได้"""
    name: str = Field(min_length=1, max_length=200, index=True)
    slug: str = Field(min_length=1, max_length=200, unique=True, index=True)
    description: Optional[str] = Field(default=None, max_length=2000)
    version: str = Field(default="0.1.0", max_length=20)
    entry_point: str = Field(default="main", max_length=200)
    enabled: bool = Field(default=False)
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    dependencies: Optional[str] = Field(default=None, max_length=500, description="plugin slugs ที่ต้องโหลดก่อน คั่นด้วย comma")


class Plugin(PluginBase, TimestampMixin, table=True):
    __tablename__ = "plugin"
    id: Optional[int] = Field(default=None, primary_key=True)


class PluginCreate(PluginBase):
    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        return _validate_slug(v)


class PluginUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    version: Optional[str] = Field(default=None, max_length=20)
    entry_point: Optional[str] = Field(default=None, max_length=200)
    enabled: Optional[bool] = None
    config: Optional[dict] = None
    dependencies: Optional[str] = Field(default=None, max_length=500)


class PluginRead(PluginBase):
    id: int
    created_at: datetime
    updated_at: datetime


# ─── App (Mini App) ──────────────────────────────────────────────────────

class AppBase(SQLModel):
    """Mini App ที่เชื่อมต่อผ่าน API Gateway"""
    name: str = Field(min_length=1, max_length=200, index=True)
    slug: str = Field(min_length=1, max_length=200, unique=True, index=True)
    description: Optional[str] = Field(default=None, max_length=2000)
    version: str = Field(default="0.1.0", max_length=20)
    base_url: Optional[str] = Field(default=None, max_length=500)
    api_key_hash: Optional[str] = Field(default=None, max_length=256)
    enabled: bool = Field(default=False)
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))


class App(AppBase, TimestampMixin, table=True):
    __tablename__ = "app"
    id: Optional[int] = Field(default=None, primary_key=True)


class AppCreate(AppBase):
    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        return _validate_slug(v)


class AppUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    version: Optional[str] = Field(default=None, max_length=20)
    base_url: Optional[str] = Field(default=None, max_length=500)
    enabled: Optional[bool] = None
    config: Optional[dict] = None


class AppRead(AppBase):
    id: int
    created_at: datetime
    updated_at: datetime
