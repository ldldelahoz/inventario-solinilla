import sqlite3
import os
from pathlib import Path

# Render monta /data como volumen persistente. Fallback a local para pruebas.
DB_PATH = Path(os.getenv("DB_PATH", "/data/solinilla.db"))

def get_conn():
    # ✅ Solo intentar crear el directorio si NO es /data (que ya existe en Render)
    # O si estamos en local (donde sí necesitamos crearlo)
    if not DB_PATH.parent.exists() and str(DB_PATH.parent) != "/data":
        try:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            # En Render, /data ya debería existir. Si no, usamos la ruta tal cual.
            print(f"⚠️ No se pudo crear {DB_PATH.parent}: {e}")
    
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
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
    except Exception as e:
        import sys
        print(f"❌ ERROR en init_db: {e}", file=sys.stderr)
        raise