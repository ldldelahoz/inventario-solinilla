import os
import sys
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import timedelta
from contextlib import asynccontextmanager
from typing import Optional

# 🔹 Imports de tus módulos locales
from src.db import init_db, get_conn
from src.auth import (
    create_access_token, verify_password, hash_password,
    get_current_user, require_admin, ACCESS_TOKEN_EXPIRE_MINUTES
)
from src import inventory

# 📝 Helper para logs visibles en Render
def log_error(msg: str):
    print(f" LOG: {msg}", file=sys.stderr)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        log_error("Iniciando base de datos...")
        init_db()
        log_error("✅ Base de datos lista.")
    except Exception as e:
        log_error(f"💥 Error crítico en BD: {e}")
        raise
    yield

app = FastAPI(title="🍽️ Restaurante Solinilla", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

# 📦 Modelos
class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    rol: str = "usuario"

class ProductoCreate(BaseModel):
    id: str
    nombre: str
    fecha_vencimiento: Optional[str] = ""

class MovimientoCreate(BaseModel):
    id_prod: str
    tipo: str
    cantidad: float
    motivo: str

#  Rutas Web
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# 🧪 API: Test
@app.get("/api/test")
def api_test():
    return {"status": "online", "msg": "Solinilla Backend OK"}

# 🔐 API: Login
@app.post("/api/login")
async def login(data: LoginRequest):
    log_error(f"Intento de login: {data.username}")
    with get_conn() as conn:
        user = conn.execute("SELECT * FROM usuarios WHERE username=?", (data.username,)).fetchone()
    
    # Si no hay user y es admin, lo creamos al vuelo (solo primera vez)
    if not user and data.username.lower() == "admin" and data.password == "Solinilla2026!":
        hashed = hash_password("Solinilla2026!")
        with get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO usuarios (username, password_hash, rol) VALUES (?, ?, ?)",
                         ("admin", hashed, "admin"))
            conn.commit()
        user = conn.execute("SELECT * FROM usuarios WHERE username=?", ("admin",)).fetchone()
        log_error("✅ Usuario admin creado automáticamente.")

    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token = create_access_token(
        data={"sub": user["username"], "rol": user["rol"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": token, "token_type": "bearer", "rol": user["rol"]}

# 🛠️ API: Debug para crear admin manualmente (Si falla el login automático)
@app.post("/api/debug/crear-admin")
async def crear_admin_debug():
    """Crea admin manualmente con contraseña compatible con bcrypt."""
    from src.auth import hash_password
    try:
        # 🔹 Usamos contraseña corta para evitar límite de 72 bytes de bcrypt
        password_temp = "Admin2026!"  
        hashed = hash_password(password_temp)
        
        with get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO usuarios (username, password_hash, rol) 
                VALUES (?, ?, ?)
            """, ("admin", hashed, "admin"))
            conn.commit()
        return {
            "msg": "✅ Admin creado exitosamente.",
            "nota": f"Usa contraseña temporal: {password_temp}"
        }
    except Exception as e:
        return {"msg": f"❌ Error: {str(e)}"}
#  API: Crear usuario (Solo Admin)
@app.post("/api/admin/crear-usuario")
async def crear_usuario(data: UserCreate, admin: dict = Depends(require_admin)):
    with get_conn() as conn:
        try:
            hashed = hash_password(data.password)
            conn.execute("INSERT INTO usuarios (username, password_hash, rol) VALUES (?, ?, ?)",
                         (data.username, hashed, data.rol))
            return {"msg": f"✅ Usuario {data.username} creado."}
        except Exception:
            raise HTTPException(status_code=400, detail="El usuario ya existe.")

# 📦 API: Inventario
@app.get("/api/productos")
async def get_productos(user: dict = Depends(get_current_user)):
    return {"productos": inventory.obtener_productos()}

@app.post("/api/productos")
async def crear_prod(data: ProductoCreate, user: dict = Depends(require_admin)):
    ok, msg = inventory.crear_producto(data.id, data.nombre, data.fecha_vencimiento)
    if not ok: raise HTTPException(status_code=400, detail=msg)
    return {"msg": msg}

@app.post("/api/movimientos")
async def registrar_mov(data: MovimientoCreate, user: dict = Depends(get_current_user)):
    ok, msg = inventory.registrar_movimiento(data.id_prod, data.tipo, data.cantidad, data.motivo)
    if not ok: raise HTTPException(status_code=400, detail=msg)
    return {"msg": msg}

@app.get("/api/reporte")
async def get_reporte(fecha: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    return inventory.generar_reporte(fecha)

@app.get("/api/productos/buscar")
async def buscar_prods(q: str = Query(..., min_length=1), user: dict = Depends(get_current_user)):
    return {"productos": inventory.buscar_productos(q)}

@app.get("/api/movimientos/dia")
async def get_movimientos_dia(fecha: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    return {"movimientos": inventory.obtener_movimientos_dia(fecha)}

@app.put("/api/movimientos/{mov_id}")
async def put_movimiento(mov_id: int, data: MovimientoCreate, user: dict = Depends(require_admin)):
    ok, msg = inventory.editar_movimiento(mov_id, data.cantidad, data.motivo)
    if not ok: raise HTTPException(status_code=400, detail=msg)
    return {"msg": msg}

@app.delete("/api/movimientos/{mov_id}")
async def delete_movimiento(mov_id: int, user: dict = Depends(require_admin)):
    ok, msg = inventory.eliminar_movimiento(mov_id)
    if not ok: raise HTTPException(status_code=400, detail=msg)
    return {"msg": msg}

@app.post("/api/inventario/cerrar")
async def cerrar_inv(data: dict, user: dict = Depends(require_admin)):
    ok, msg = inventory.cerrar_inventario_dia(data.get("fecha"), data.get("observaciones", ""))
    if not ok: raise HTTPException(status_code=400, detail=msg)
    return {"msg": msg}

@app.get("/api/hoja-inventario")
async def get_hoja_impresion(fecha: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    return inventory.generar_hoja_impresion(fecha)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))