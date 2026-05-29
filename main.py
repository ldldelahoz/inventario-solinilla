from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import timedelta
from contextlib import asynccontextmanager
from typing import Optional
import os

# ✅ Imports de tus módulos (solo importamos, no ejecutamos aún)
from src.db import init_db, get_conn
from src.auth import (
    create_access_token, verify_password, hash_password,
    get_current_user, require_admin, ACCESS_TOKEN_EXPIRE_MINUTES
)
from src import inventory

app = FastAPI(title="Solinilla")  # Sin lifespan por ahora

# Rutas mínimas para probar
@app.get("/")
def root():
    return {"msg": "Solinilla - Imports OK"}

@app.get("/api/test")
def test():
    return {"status": "online", "msg": "Imports loaded"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))