import sys
import os
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import timedelta
from contextlib import asynccontextmanager
from typing import Optional

# Imports de tus módulos
from src.db import init_db, get_conn
from src.auth import (
    create_access_token, verify_password, hash_password,
    get_current_user, require_admin, ACCESS_TOKEN_EXPIRE_MINUTES
)
from src import inventory

# ✅ Logging helper para asegurar que los errores se vean en Render
def log_error(msg: str):
    print(f"❌ SOLINILLA ERROR: {msg}", file=sys.stderr)
    sys.stderr.flush()

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        log_error("Iniciando lifespan: llamando a init_db()...")
        init_db()
        log_error("✅ init_db() completado exitosamente")
    except Exception as e:
        log_error(f"💥 FALLO CRÍTICO en init_db: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise  # Relanzar para que uvicorn detecte el fallo
    yield

app = FastAPI(title="Solinilla", lifespan=lifespan)

# ✅ Templates con ruta relativa simple
templates = Jinja2Templates(directory="templates")

class LoginRequest(BaseModel):
    username: str
    password: str

# 🌐 Rutas Web con manejo de errores explícito
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    try:
        # Sintaxis compatible con FastAPI 0.100+
        return templates.TemplateResponse("login.html", {"request": request})
    except Exception as e:
        log_error(f"Error cargando login.html: {e}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1><p>Revisa los deploy logs</p>", status_code=500)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        log_error(f"Error cargando dashboard.html: {e}")
        return HTMLResponse(content="<h1>Dashboard no disponible</h1>", status_code=500)

# 🧪 Rutas API de prueba
@app.get("/api/test")
def api_test():
    return {"status": "online", "msg": "Solinilla - BD + Templates + Logging OK"}

@app.post("/api/login")
async def login(data: LoginRequest):
    try:
        log_error(f"Intento de login para usuario: {data.username}")
        with get_conn() as conn:
            user = conn.execute("SELECT * FROM usuarios WHERE username=?", (data.username,)).fetchone()
        
        # Crear admin por defecto si no existe
        if not user and data.username.lower() == "admin" and data.password == "Solinilla2026!":
            hashed = hash_password("Solinilla2026!")
            with get_conn() as conn:
                conn.execute("INSERT OR IGNORE INTO usuarios (username, password_hash, rol) VALUES (?, ?, ?)",
                             ("admin", hashed, "admin"))
                conn.commit()
            user = conn.execute("SELECT * FROM usuarios WHERE username=?", ("admin",)).fetchone()
            log_error("✅ Usuario admin creado automáticamente")

        if not user or not verify_password(data.password, user["password_hash"]):
            log_error("❌ Credenciales incorrectas")
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

        token = create_access_token(
            data={"sub": user["username"], "rol": user["rol"]},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        log_error(f"✅ Login exitoso para {user['username']}")
        return {"access_token": token, "token_type": "bearer", "rol": user["rol"]}
    except Exception as e:
        log_error(f"💥 Error en /api/login: {e}")
        raise

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    log_error(f"🚀 Arrancando uvicorn en puerto {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)