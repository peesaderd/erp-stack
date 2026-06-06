"""Shared SQLAlchemy models — users, sessions, products, transactions, media"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, Enum as SAEnum, JSON
from sqlalchemy.orm import relationship
from shared.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


# ──────────────────────────────────────────────
# User / Auth
# ──────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    avatar_url = Column(String, default="")
    password_hash = Column(String, default="")  # empty for OAuth users
    member_tier = Column(String, default="bronze")  # bronze, silver, gold, ultra
    credits = Column(Float, default=0.0)
    credits_used = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    auth_providers = relationship("AuthProvider", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    provider = Column(String, default="")  # "email", "google", "facebook", "line"
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    user = relationship("User", back_populates="sessions")


class AuthProvider(Base):
    __tablename__ = "auth_providers"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String, nullable=False)  # "google", "facebook", "line"
    provider_user_id = Column(String, nullable=False)
    provider_email = Column(String, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    user = relationship("User", back_populates="auth_providers")


# ──────────────────────────────────────────────
# Payment / Credits
# ──────────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="THB")
    payment_method = Column(String, default="")  # "stripe", "qrcode", "promptpay"
    payment_ref = Column(String, default="")
    status = Column(String, default="pending")  # pending, completed, failed, refunded
    description = Column(String, default="")
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="transactions")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    tier = Column(String, nullable=False)  # bronze, silver, gold, ultra
    status = Column(String, default="active")  # active, cancelled, expired
    start_date = Column(DateTime(timezone=True), default=_utcnow)
    end_date = Column(DateTime(timezone=True), nullable=True)
    auto_renew = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


# ──────────────────────────────────────────────
# Media
# ──────────────────────────────────────────────

class Media(Base):
    __tablename__ = "media"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    original_name = Column(String, default="")
    mime_type = Column(String, default="")
    size_bytes = Column(Integer, default=0)
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)
    url = Column(String, default="")
    thumbnail_url = Column(String, default="")
    category = Column(String, default="")  # product, reference, output, avatar
    tags = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


# ──────────────────────────────────────────────
# Product / Stock
# ──────────────────────────────────────────────

class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    sku = Column(String, default="")
    barcode = Column(String, default="")
    price = Column(Float, default=0.0)
    cost_price = Column(Float, default=0.0)
    category = Column(String, default="")
    tags = Column(JSON, default=list)
    source_url = Column(String, default="")  # original Shopee/Lazada URL
    image_urls = Column(JSON, default=list)  # array of media URLs
    ai_analysis = Column(JSON, default=dict)  # Gemini analysis result
    stock_status = Column(String, default="active")  # active, archived, out_of_stock
    generated_count = Column(Integer, default=0)  # times content was generated
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="products")


# ──────────────────────────────────────────────
# Generated Content Log
# ──────────────────────────────────────────────

class GeneratedContent(Base):
    __tablename__ = "generated_content"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=True, index=True)
    content_type = Column(String, nullable=False)  # "image", "video"
    provider = Column(String, default="")  # "fal", "wavespeed"
    model = Column(String, default="")
    prompt = Column(Text, default="")
    result_url = Column(String, default="")
    thumbnail_url = Column(String, default="")
    cost = Column(Float, default=0.0)
    status = Column(String, default="completed")  # pending, processing, completed, failed
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
