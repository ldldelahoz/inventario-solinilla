from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import timedelta
from contextlib import asynccontextmanager
from typing import Optional
import os

from src.db import init_db, get_conn
from src.auth import (
    create_access_token, verify_password, hash_password,
    get_current_user, require_admin, ACCESS_TOKEN_EXPIRE_MINUTES
)
from src import inventory

# ✅ Lifespan: inicializa BD al arrancar el servidor
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # Crea tablas si no existen
    yield

app = FastAPI(title="🍽️ Sistema de Inventarios Restaurante Solinilla", lifespan=lifespan)

# ✅ Templates: ruta relativa (Render busca en la carpeta 'templates' del repo)
templates = Jinja2Templates(directory="templates")

class LoginRequest(BaseModel):
    username: str
    password: str

# 🌐 Rutas Web con templates
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html", context={})

# 🧪 Rutas de prueba API
@app.get("/api/test")
def api_test():
    return {"status": "online", "msg": "Solinilla - BD + Templates OK"}

@app.post("/api/login")
async def login(data: LoginRequest):
    # Versión mínima para probar que la BD responde
    with get_conn() as conn:
        user = conn.execute("SELECT * FROM usuarios WHERE username=?", (data.username,)).fetchone()
    
    if not user and data.username.lower() == "admin" and data.password == "Solinilla2026!":
        hashed = hash_password("Solinilla2026!")
        with get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO usuarios (username, password_hash, rol) VALUES (?, ?, ?)",
                         ("admin", hashed, "admin"))
        user = conn.execute("SELECT * FROM usuarios WHERE username=?", ("admin",)).fetchone()

    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token = create_access_token(
        data={"sub": user["username"], "rol": user["rol"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": token, "token_type": "bearer", "rol": user["rol"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))