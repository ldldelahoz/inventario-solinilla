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

from src.db import init_db, get_conn
from src.auth import (
    create_access_token, verify_password, hash_password,
    get_current_user, require_admin, ACCESS_TOKEN_EXPIRE_MINUTES
)
from src import inventory

def log_error(msg: str):
    print(f" LOG: {msg}", file=sys.stderr)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        log_error("Iniciando BD...")
        init_db()
        log_error("✅ BD lista")
    except Exception as e:
        log_error(f"💥 Error BD: {e}")
        raise
    yield

app = FastAPI(title="🍽️ Solinilla", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

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

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/api/test")
def api_test():
    return {"status": "online", "msg": "Solinilla OK"}

@app.post("/api/login")
async def login(data: LoginRequest):
    log_error(f"Login: {data.username}")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE username=%s", (data.username,))
            user = cur.fetchone()
        
        if not user and data.username.lower() == "admin" and data.password == "Admin2026!":
            hashed = hash_password("Admin2026!")
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO usuarios (username, password_hash, rol) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (username) DO NOTHING
                """, ("admin", hashed, "admin"))
                conn.commit()
            cur.execute("SELECT * FROM usuarios WHERE username=%s", ("admin",))
            user = cur.fetchone()
            log_error("✅ Admin creado")

        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")

        token = create_access_token(
            data={"sub": user["username"], "rol": user["rol"]},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": token, "token_type": "bearer", "rol": user["rol"]}

@app.post("/api/debug/crear-admin")
async def crear_admin_debug():
    try:
        hashed = hash_password("Admin2026!")
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO usuarios (username, password_hash, rol) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (username) DO NOTHING
                """, ("admin", hashed, "admin"))
                conn.commit()
        return {"msg": "✅ Admin creado. Login: admin / Admin2026!"}
    except Exception as e:
        return {"msg": f"❌ Error: {str(e)}"}

@app.post("/api/admin/crear-usuario")
async def crear_usuario(data: UserCreate, admin: dict = Depends(require_admin)):
    with get_conn() as conn:
        try:
            hashed = hash_password(data.password)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO usuarios (username, password_hash, rol) 
                    VALUES (%s, %s, %s)
                """, (data.username, hashed, data.rol))
                conn.commit()
            return {"msg": f"✅ Usuario {data.username} creado"}
        except Exception:
            raise HTTPException(status_code=400, detail="Usuario ya existe")

@app.get("/api/productos")
async def get_productos(user: dict = Depends(get_current_user)):
    return {"productos": inventory.obtener_productos()}

@app.post("/api/productos")
async def crear_prod(data: ProductoCreate, user: dict = Depends(require_admin)):
    ok, msg = inventory.crear_producto(data.id, data.nombre, data.fecha_vencimiento)
    if not ok: raise HTTPException(status_code=400, detail=msg)
    return {"msg": msg}
@app.delete("/api/productos/{producto_id}")
async def delete_producto(producto_id: str, current_user: dict = Depends(get_current_user)):
    """Elimina un producto por su ID."""
    try:
        from src.inventory import eliminar_producto
        success, msg = eliminar_producto(producto_id)
        if success:
            return {"msg": msg}
        raise HTTPException(status_code=400, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
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

# --- Agrega esto a main.py si no está ---

@app.post("/api/inventario/cerrar")
async def cerrar_inventario(fecha: str, observaciones: str = "", current_user: dict = Depends(get_current_user)):
    """Cierra el inventario del día y guarda el snapshot."""
    try:
        # Importamos la función del archivo de inventario
        from src.inventory import cerrar_inventario_dia
        success, msg = cerrar_inventario_dia(fecha, observaciones)
        if success:
            return {"msg": msg}
        else:
            raise HTTPException(status_code=400, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/movimientos")
async def obtener_movimientos(fecha: str = None, current_user: dict = Depends(get_current_user)):
    """Obtiene movimientos, filtrando por fecha si se provee."""
    from datetime import date
    if not fecha:
        fecha = date.today().isoformat()
        
    from src.inventory import obtener_movimientos_dia
    movimientos = obtener_movimientos_dia(fecha)
    return {"movimientos": movimientos}

@app.get("/api/hoja-inventario")
async def get_hoja_impresion(fecha: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    return inventory.generar_hoja_impresion(fecha)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))