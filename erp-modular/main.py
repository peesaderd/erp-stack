"""ERP Modular - FastAPI Application"""

from fastapi import FastAPI
from api.router import router
from core.database import init_db

app = FastAPI(title="ERP Modular", version="0.1.0")
app.include_router(router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
