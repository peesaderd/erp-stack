"""Core Data Models for ERP Modular - Pydantic v2 + SQLModel"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column, JSON
from pydantic import BaseModel


# ─── Base ────────────────────────────────────────────────────────────────

class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow})


# ─── Entity ──────────────────────────────────────────────────────────────

class EntityBase(SQLModel):
    """สิ่งของในระบบ เช่น Customer, Invoice, Product, Order"""
    name: str = Field(index=True)
    slug: str = Field(unique=True, index=True)
    description: Optional[str] = None
    module_id: Optional[int] = Field(default=None, foreign_key="module.id")
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Entity(EntityBase, TimestampMixin, table=True):
    __tablename__ = "entity"
    id: Optional[int] = Field(default=None, primary_key=True)


class EntityCreate(EntityBase):
    pass


class EntityRead(EntityBase):
    id: int
    created_at: datetime
    updated_at: datetime


# ─── Module ──────────────────────────────────────────────────────────────

class ModuleBase(SQLModel):
    """กลุ่มของ Entity ที่ทำงานร่วมกัน เช่น Accounting, CRM, Inventory"""
    name: str = Field(index=True)
    slug: str = Field(unique=True, index=True)
    description: Optional[str] = None
    version: str = Field(default="0.1.0")
    enabled: bool = Field(default=True)
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Module(ModuleBase, TimestampMixin, table=True):
    __tablename__ = "module"
    id: Optional[int] = Field(default=None, primary_key=True)


class ModuleCreate(ModuleBase):
    pass


class ModuleRead(ModuleBase):
    id: int
    created_at: datetime
    updated_at: datetime


# ─── Template ────────────────────────────────────────────────────────────

class TemplateBase(SQLModel):
    """แม่แบบสำหรับสร้าง Entity หรือ Module ซ้ำ"""
    name: str = Field(index=True)
    slug: str = Field(unique=True, index=True)
    description: Optional[str] = None
    template_type: str = Field(default="entity")  # "entity" | "module" | "plugin"
    schema_def: dict = Field(default_factory=dict, sa_column=Column(JSON))
    module_id: Optional[int] = Field(default=None, foreign_key="module.id")


class Template(TemplateBase, TimestampMixin, table=True):
    __tablename__ = "template"
    id: Optional[int] = Field(default=None, primary_key=True)


class TemplateCreate(TemplateBase):
    pass


class TemplateRead(TemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime


# ─── Plugin ──────────────────────────────────────────────────────────────

class PluginBase(SQLModel):
    """ส่วนขยายที่แทรกเข้าไปในระบบได้"""
    name: str = Field(index=True)
    slug: str = Field(unique=True, index=True)
    description: Optional[str] = None
    version: str = Field(default="0.1.0")
    entry_point: str = Field(default="main")
    enabled: bool = Field(default=False)
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Plugin(PluginBase, TimestampMixin, table=True):
    __tablename__ = "plugin"
    id: Optional[int] = Field(default=None, primary_key=True)


class PluginCreate(PluginBase):
    pass


class PluginRead(PluginBase):
    id: int
    created_at: datetime
    updated_at: datetime


# ─── App (Mini App) ──────────────────────────────────────────────────────

class AppBase(SQLModel):
    """Mini App ที่เชื่อมต่อผ่าน API Gateway"""
    name: str = Field(index=True)
    slug: str = Field(unique=True, index=True)
    description: Optional[str] = None
    version: str = Field(default="0.1.0")
    base_url: Optional[str] = None
    api_key_hash: Optional[str] = None
    enabled: bool = Field(default=False)
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))


class App(AppBase, TimestampMixin, table=True):
    __tablename__ = "app"
    id: Optional[int] = Field(default=None, primary_key=True)


class AppCreate(AppBase):
    pass


class AppRead(AppBase):
    id: int
    created_at: datetime
    updated_at: datetime
