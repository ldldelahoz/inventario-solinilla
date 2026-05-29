import sqlite3
import os
import sys
from pathlib import Path

def log(msg: str):
    print(f"🗄️ DB: {msg}", file=sys.stderr)
    sys.stderr.flush()

# ✅ Lógica robusta para determinar la ruta de la BD
def get_db_path():
    # Si Render define DB_PATH como variable de entorno, úsala
    if os.getenv("DB_PATH"):
        return Path(os.getenv("DB_PATH"))
    
    # En Render, intentamos /data/solinilla.db primero
    if os.getenv("PORT"):  # Detectamos que estamos en Render
        render_path = Path("/data/solinilla.db")
        # Verificar si podemos escribir en /data
        try:
            if render_path.parent.exists() and os.access(render_path.parent, os.W_OK):
                log(f"Usando ruta Render: {render_path}")
                return render_path
        except:
            pass
        # Fallback a ruta relativa (no persistente, pero funcional para pruebas)
        log("⚠️ /data no accesible, usando ruta relativa (no persistente en Render)")
        return Path("solinilla.db")
    
    # Local: usar carpeta data en el proyecto
    local_path = Path("data/solinilla.db")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    log(f"Usando ruta local: {local_path}")
    return local_path

DB_PATH = get_db_path()

def get_conn():
    # Intentar conectar con retry logic
    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            log(f"✅ Conexión exitosa a {DB_PATH}")
            return conn
        except sqlite3.OperationalError as e:
            last_error = e
            log(f"⚠️ Intento {attempt+1}/{max_retries} fallido: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(0.5)
    
    # Si todos los intentos fallaron
    log(f"❌ No se pudo conectar a la BD después de {max_retries} intentos")
    raise last_error

def init_db():
    log(f"Iniciando init_db() con ruta: {DB_PATH}")
    try:
        with get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    rol TEXT NOT NULL DEFAULT 'usuario' CHECK(rol IN ('admin', 'usuario')),
                    creado_en TEXT DEFAULT (datetime('now','localtime'))
                );
                CREATE TABLE IF NOT EXISTS productos (
                    id TEXT PRIMARY KEY,
                    nombre TEXT NOT NULL,
                    stock REAL NOT NULL DEFAULT 0,
                    fecha_vencimiento TEXT
                );
                CREATE TABLE IF NOT EXISTS movimientos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    producto_id TEXT NOT NULL,
                    tipo TEXT NOT NULL CHECK(tipo IN ('entrada', 'salida')),
                    cantidad REAL NOT NULL,
                    motivo TEXT,
                    fecha TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS snapshots_inventario (
                    fecha TEXT NOT NULL,
                    producto_id TEXT NOT NULL,
                    stock_cierre REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (fecha, producto_id),
                    FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS cierres_inventario (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL,
                    total_movimientos INTEGER,
                    total_productos INTEGER,
                    observaciones TEXT,
                    creado_en TEXT DEFAULT (datetime('now','localtime'))
                );
            """)
            conn.commit()
        log("✅ init_db() completado exitosamente")
    except Exception as e:
        log(f"💥 ERROR en init_db: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise