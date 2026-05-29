import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

def log(msg: str):
    print(f"🗄️ {msg}", file=sys.stderr)
    sys.stderr.flush()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL no configurada")

log(f"🌐 Conectando a PostgreSQL...")

@contextmanager
def get_conn():
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor_factory = RealDictCursor
        log("✅ Conexión exitosa")
        yield conn
    except Exception as e:
        log(f"❌ Error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_db():
    log("🔧 Creando tablas...")
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS usuarios (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        rol TEXT NOT NULL DEFAULT 'usuario' CHECK(rol IN ('admin', 'usuario')),
                        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS productos (
                        id TEXT PRIMARY KEY,
                        nombre TEXT NOT NULL,
                        stock REAL NOT NULL DEFAULT 0,
                        fecha_vencimiento TEXT
                    )
                """)
                
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS movimientos (
                        id SERIAL PRIMARY KEY,
                        producto_id TEXT NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
                        tipo TEXT NOT NULL CHECK(tipo IN ('entrada', 'salida')),
                        cantidad REAL NOT NULL,
                        motivo TEXT,
                        fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS snapshots_inventario (
                        fecha DATE NOT NULL,
                        producto_id TEXT NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
                        stock_cierre REAL NOT NULL DEFAULT 0,
                        PRIMARY KEY (fecha, producto_id)
                    )
                """)
                
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS cierres_inventario (
                        id SERIAL PRIMARY KEY,
                        fecha DATE NOT NULL,
                        total_movimientos INTEGER,
                        total_productos INTEGER,
                        observaciones TEXT,
                        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
        log("✅ Tablas creadas")
    except Exception as e:
        log(f"💥 ERROR: {e}")
        raise