# JWT Gateway Service

import os
import time
from datetime import datetime, timedelta
from typing import Dict

import jwt  # PyJWT
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="JWT Gateway")

JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey")
JWT_ALG = "HS256"
TOKEN_EXP_SECONDS = int(os.getenv("TOKEN_EXP_SECONDS", "3600"))  # 1 hour

def create_jwt(payload: Dict) -> str:
    now = datetime.utcnow()
    payload.update({"iat": now, "exp": now + timedelta(seconds=TOKEN_EXP_SECONDS)})
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)
    return token

@app.post("/api/v1/auth/token")
async def issue_token(authorization: str = Header(...)):
    # In real world, validate the OAuth token (Google/Facebook/LINE) here.
    # For this prototype we accept any non‑empty token and extract a dummy user_id.
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=400, detail="Invalid Authorization header")
    oauth_token = authorization.split(" ", 1)[1]
    # Mock validation – treat token string as user identifier
    user_id = oauth_token[:8]  # first 8 chars as mock ID
    jwt_token = create_jwt({"sub": user_id})
    return JSONResponse({"access_token": jwt_token, "token_type": "bearer"})

@app.get("/health")
async def health():
    return JSONResponse({"status": "jwt gateway ok"})
