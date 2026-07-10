# Product Loop Service (PostgreSQL + SQLAlchemy)

import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sqlalchemy import (Column, Integer, String, DateTime, JSON, create_engine,
                        func, select)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/productdb")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    data = Column(JSON)  # arbitrary product data

class Usage(Base):
    __tablename__ = "usage"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Product Loop Service")

# Pydantic schemas
class ProductCreate(BaseModel):
    name: str
    data: Optional[dict] = None

class ProductOut(BaseModel):
    id: int
    name: str
    data: Optional[dict]

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/v1/product", response_model=ProductOut)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    db_product = Product(name=product.name, data=product.data)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@app.get("/api/v1/product/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    return prod

@app.get("/api/v1/products", response_model=List[ProductOut])
def list_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Product).offset(skip).limit(limit).all()

# Usage tracking
MAX_USES = int(os.getenv("MAX_USES_PER_30D", "3"))
WINDOW_DAYS = int(os.getenv("USAGE_WINDOW_DAYS", "30"))

@app.post("/api/v1/usage/{user_id}")
def record_usage(user_id: str, db: Session = Depends(get_db)):
    # Count usages in the last WINDOW_DAYS
    cutoff = datetime.utcnow() - timedelta(days=WINDOW_DAYS)
    count = db.query(Usage).filter(Usage.user_id == user_id, Usage.created_at >= cutoff).count()
    if count >= MAX_USES:
        raise HTTPException(status_code=429, detail="Usage limit exceeded")
    usage = Usage(user_id=user_id)
    db.add(usage)
    db.commit()
    return JSONResponse({"status": "recorded", "current_count": count + 1})

@app.get("/api/v1/usage/{user_id}")
def get_usage(user_id: str, db: Session = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(days=WINDOW_DAYS)
    count = db.query(Usage).filter(Usage.user_id == user_id, Usage.created_at >= cutoff).count()
    return JSONResponse({"user_id": user_id, "usage_last_30d": count, "max_allowed": MAX_USES})

@app.get("/health")
def health():
    return JSONResponse({"status": "product loop ok"})
