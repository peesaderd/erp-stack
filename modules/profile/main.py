"""Profile Module — Business & Client Profile Management (port 8107)
    
เชื่อมกับ ERP Modular Registry + Shared DB models
รองรับ:
- Business/Tenant profile (company info, branding, config)
- Client/Customer profile (CRM basics)
- Contact management
- Address management
- Profile image upload (เชื่อม Media Module :8103)
"""

import os, sys, json, logging, uuid
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Path setup
_module_dir = os.path.dirname(os.path.abspath(__file__))
_modules_dir = os.path.dirname(_module_dir)
if _modules_dir not in sys.path:
    sys.path.insert(0, _modules_dir)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("profile_module")

# ──────────────────────────────────────────────
# In-memory storage (for MVP — replace with DB later)
# ──────────────────────────────────────────────

profiles_store: dict = {}        # profile_id -> profile
businesses_store: dict = {}      # business_id -> business
clients_store: dict = {}         # client_id -> client
contacts_store: dict = {}        # contact_id -> contact
addresses_store: dict = {}       # address_id -> address

# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────

class AddressBase(BaseModel):
    label: str = ""
    line1: str
    line2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = "TH"
    is_primary: bool = False

class AddressCreate(AddressBase): pass

class Address(AddressBase):
    id: str
    owner_type: str  # "business", "client"
    owner_id: str
    created_at: str
    updated_at: str

class ContactBase(BaseModel):
    name: str
    role: str = ""
    email: str = ""
    phone: str = ""
    is_primary: bool = False

class ContactCreate(ContactBase): pass

class Contact(ContactBase):
    id: str
    owner_type: str  # "business", "client"
    owner_id: str
    created_at: str
    updated_at: str

class BusinessProfile(BaseModel):
    id: str = ""
    name: str
    slug: str = ""
    tax_id: str = ""
    industry: str = ""
    description: str = ""
    logo_url: str = ""
    website: str = ""
    phone: str = ""
    email: str = ""
    social_links: dict = {}
    config: dict = {}  # business-specific config (e.g., PromptPay number)
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""

class ClientProfile(BaseModel):
    id: str = ""
    name: str
    email: str = ""
    phone: str = ""
    avatar_url: str = ""
    notes: str = ""
    tags: list = []
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""

class ProfileResponse(BaseModel):
    ok: bool = True
    data: Optional[dict] = None
    items: Optional[list] = None
    total: int = 0
    message: str = ""

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _uuid():
    return str(uuid.uuid4())

def _utcnow():
    return datetime.now(timezone.utc).isoformat()

def _slugify(name: str) -> str:
    import re
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')

# ──────────────────────────────────────────────
# Registration with ERP Modular
# ──────────────────────────────────────────────

async def register_with_erp():
    """Register this module with ERP Modular at startup."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                "http://localhost:8102/api/v1/modules/register",
                json={
                    "name": "Profile Module",
                    "slug": "profile",
                    "version": "1.0.0",
                    "endpoint": "http://localhost:8107",
                    "description": "Business & Client Profile Management",
                }
            )
            logger.info(f"Registered with ERP Modular: {resp.status_code}")
    except Exception as e:
        logger.warning(f"ERP registration failed: {e} — will retry on next startup")

# ──────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Profile Module starting on port 8107")
    await register_with_erp()
    yield
    logger.info("Profile Module shutting down")

app = FastAPI(title="Profile Module", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ──────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "profile-module", "version": "1.0.0"}

# ══════════════════════════════════════════════
# Business Profile CRUD
# ══════════════════════════════════════════════

@app.post("/api/v1/profiles/business", response_model=ProfileResponse)
async def create_business(profile: BusinessProfile):
    """สร้าง Business Profile ใหม่"""
    profile_id = _uuid()
    now = _utcnow()
    data = profile.model_dump()
    data["id"] = profile_id
    data["slug"] = data["slug"] or _slugify(data["name"])
    data["created_at"] = now
    data["updated_at"] = now
    businesses_store[profile_id] = data
    logger.info(f"Business created: {data['name']} ({profile_id})")
    return ProfileResponse(data=data)

@app.get("/api/v1/profiles/business", response_model=ProfileResponse)
async def list_businesses(search: str = Query(""), limit: int = Query(50, le=200), offset: int = Query(0)):
    """รายการ Business Profiles ทั้งหมด"""
    items = list(businesses_store.values())
    if search:
        search = search.lower()
        items = [b for b in items if search in b["name"].lower() or search in b.get("slug", "").lower()]
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return ProfileResponse(items=items[offset:offset+limit], total=len(items))

@app.get("/api/v1/profiles/business/{profile_id}", response_model=ProfileResponse)
async def get_business(profile_id: str):
    """ดู Business Profile ตาม ID"""
    data = businesses_store.get(profile_id)
    if not data:
        raise HTTPException(404, "Business not found")
    return ProfileResponse(data=data)

@app.put("/api/v1/profiles/business/{profile_id}", response_model=ProfileResponse)
async def update_business(profile_id: str, profile: BusinessProfile):
    """อัปเดต Business Profile"""
    existing = businesses_store.get(profile_id)
    if not existing:
        raise HTTPException(404, "Business not found")
    update_data = profile.model_dump(exclude_unset=True)
    update_data["updated_at"] = _utcnow()
    existing.update({k: v for k, v in update_data.items() if v is not None})
    businesses_store[profile_id] = existing
    return ProfileResponse(data=existing)

@app.delete("/api/v1/profiles/business/{profile_id}", response_model=ProfileResponse)
async def delete_business(profile_id: str):
    """ลบ Business Profile"""
    if profile_id not in businesses_store:
        raise HTTPException(404, "Business not found")
    del businesses_store[profile_id]
    return ProfileResponse(message="Deleted", data={"id": profile_id})

# ══════════════════════════════════════════════
# Client Profile CRUD
# ══════════════════════════════════════════════

@app.post("/api/v1/profiles/client", response_model=ProfileResponse)
async def create_client(client: ClientProfile):
    """สร้าง Client Profile ใหม่"""
    client_id = _uuid()
    now = _utcnow()
    data = client.model_dump()
    data["id"] = client_id
    data["created_at"] = now
    data["updated_at"] = now
    clients_store[client_id] = data
    logger.info(f"Client created: {data['name']} ({client_id})")
    return ProfileResponse(data=data)

@app.get("/api/v1/profiles/client", response_model=ProfileResponse)
async def list_clients(search: str = Query(""), limit: int = Query(50, le=200), offset: int = Query(0)):
    items = list(clients_store.values())
    if search:
        search = search.lower()
        items = [c for c in items if search in c["name"].lower() or search in c.get("email", "").lower()]
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return ProfileResponse(items=items[offset:offset+limit], total=len(items))

@app.get("/api/v1/profiles/client/{client_id}", response_model=ProfileResponse)
async def get_client(client_id: str):
    data = clients_store.get(client_id)
    if not data:
        raise HTTPException(404, "Client not found")
    return ProfileResponse(data=data)

@app.put("/api/v1/profiles/client/{client_id}", response_model=ProfileResponse)
async def update_client(client_id: str, client: ClientProfile):
    existing = clients_store.get(client_id)
    if not existing:
        raise HTTPException(404, "Client not found")
    update_data = client.model_dump(exclude_unset=True)
    update_data["updated_at"] = _utcnow()
    existing.update({k: v for k, v in update_data.items() if v is not None})
    clients_store[client_id] = existing
    return ProfileResponse(data=existing)

@app.delete("/api/v1/profiles/client/{client_id}", response_model=ProfileResponse)
async def delete_client(client_id: str):
    if client_id not in clients_store:
        raise HTTPException(404, "Client not found")
    del clients_store[client_id]
    return ProfileResponse(message="Deleted", data={"id": client_id})

# ══════════════════════════════════════════════
# Contact CRUD (belongs to Business or Client)
# ══════════════════════════════════════════════

@app.post("/api/v1/profiles/{owner_type}/{owner_id}/contacts", response_model=ProfileResponse)
async def add_contact(owner_type: str, owner_id: str, contact: ContactCreate):
    """เพิ่ม Contact (business or client)"""
    if owner_type not in ("business", "client"):
        raise HTTPException(400, "owner_type must be 'business' or 'client'")
    store = businesses_store if owner_type == "business" else clients_store
    if owner_id not in store:
        raise HTTPException(404, f"{owner_type.title()} not found")
    contact_id = _uuid()
    now = _utcnow()
    data = contact.model_dump()
    data["id"] = contact_id
    data["owner_type"] = owner_type
    data["owner_id"] = owner_id
    data["created_at"] = now
    data["updated_at"] = now
    contacts_store[contact_id] = data
    return ProfileResponse(data=data)

@app.get("/api/v1/profiles/{owner_type}/{owner_id}/contacts", response_model=ProfileResponse)
async def list_contacts(owner_type: str, owner_id: str):
    items = [c for c in contacts_store.values() if c["owner_type"] == owner_type and c["owner_id"] == owner_id]
    return ProfileResponse(items=items, total=len(items))

# ══════════════════════════════════════════════
# Address CRUD
# ══════════════════════════════════════════════

@app.post("/api/v1/profiles/{owner_type}/{owner_id}/addresses", response_model=ProfileResponse)
async def add_address(owner_type: str, owner_id: str, address: AddressCreate):
    if owner_type not in ("business", "client"):
        raise HTTPException(400, "owner_type must be 'business' or 'client'")
    store = businesses_store if owner_type == "business" else clients_store
    if owner_id not in store:
        raise HTTPException(404, f"{owner_type.title()} not found")
    addr_id = _uuid()
    now = _utcnow()
    data = address.model_dump()
    data["id"] = addr_id
    data["owner_type"] = owner_type
    data["owner_id"] = owner_id
    data["created_at"] = now
    data["updated_at"] = now
    addresses_store[addr_id] = data
    return ProfileResponse(data=data)

@app.get("/api/v1/profiles/{owner_type}/{owner_id}/addresses", response_model=ProfileResponse)
async def list_addresses(owner_type: str, owner_id: str):
    items = [a for a in addresses_store.values() if a["owner_type"] == owner_type and a["owner_id"] == owner_id]
    return ProfileResponse(items=items, total=len(items))

# ══════════════════════════════════════════════
# ERP Integration endpoints
# ══════════════════════════════════════════════

@app.get("/api/v1/profiles/erp-sync")
async def erp_sync():
    """Export all profiles for ERP sync"""
    return {
        "businesses": list(businesses_store.values()),
        "clients": list(clients_store.values()),
        "contacts": list(contacts_store.values()),
        "addresses": list(addresses_store.values()),
    }

# ══════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════

def main():
    port = int(os.environ.get("PROFILE_PORT", 8107))
    uvicorn.run("profile.main:app", host="0.0.0.0", port=port, reload=False)

if __name__ == "__main__":
    main()
