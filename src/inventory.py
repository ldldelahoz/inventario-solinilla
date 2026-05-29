from src.db import get_conn
from datetime import date

def obtener_productos():
    with get_conn() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM productos").fetchall()]

def crear_producto(id_prod: str, nombre: str, fecha_vencimiento: str = ""):
    try:
        with get_conn() as conn:
            conn.execute("INSERT INTO productos (id, nombre, stock, fecha_vencimiento) VALUES (?, ?, 0, ?)",
                         (id_prod, nombre, fecha_vencimiento))
            conn.commit()
        return True, "✅ Producto creado"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def registrar_movimiento(id_prod: str, tipo: str, cantidad: float, motivo: str):
    try:
        with get_conn() as conn:
            conn.execute("INSERT INTO movimientos (producto_id, tipo, cantidad, motivo) VALUES (?, ?, ?, ?)",
                         (id_prod, tipo, cantidad, motivo))
            if tipo == "entrada":
                conn.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (cantidad, id_prod))
            else:
                conn.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cantidad, id_prod))
            conn.commit()
        return True, "✅ Movimiento registrado"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def generar_reporte(fecha: str = None):
    with get_conn() as conn:
        if fecha:
            rows = conn.execute("SELECT * FROM movimientos WHERE date(fecha) = ?", (fecha,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM movimientos ORDER BY fecha DESC").fetchall()
    return [dict(row) for row in rows]

def buscar_productos(q: str):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM productos WHERE id LIKE ? OR nombre LIKE ?",
                            (f"%{q}%", f"%{q}%")).fetchall()
    return [dict(row) for row in rows]

def obtener_movimientos_dia(fecha: str = None):
    fecha = fecha or date.today().isoformat()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM movimientos WHERE date(fecha) = ?", (fecha,)).fetchall()
    return [dict(row) for row in rows]

def editar_movimiento(mov_id: int, cantidad: float, motivo: str):
    try:
        with get_conn() as conn:
            old = conn.execute("SELECT producto_id, tipo, cantidad FROM movimientos WHERE id=?", (mov_id,)).fetchone()
            if not old: return False, "Movimiento no encontrado"
            if old["tipo"] == "entrada":
                conn.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (old["cantidad"], old["producto_id"]))
            else:
                conn.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (old["cantidad"], old["producto_id"]))
            conn.execute("UPDATE movimientos SET cantidad=?, motivo=? WHERE id=?", (cantidad, motivo, mov_id))
            if old["tipo"] == "entrada":
                conn.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (cantidad, old["producto_id"]))
            else:
                conn.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cantidad, old["producto_id"]))
            conn.commit()
        return True, "✅ Movimiento actualizado"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def eliminar_movimiento(mov_id: int):
    try:
        with get_conn() as conn:
            old = conn.execute("SELECT producto_id, tipo, cantidad FROM movimientos WHERE id=?", (mov_id,)).fetchone()
            if not old: return False, "Movimiento no encontrado"
            if old["tipo"] == "entrada":
                conn.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (old["cantidad"], old["producto_id"]))
            else:
                conn.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (old["cantidad"], old["producto_id"]))
            conn.execute("DELETE FROM movimientos WHERE id=?", (mov_id,))
            conn.commit()
        return True, "✅ Movimiento eliminado"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def cerrar_inventario_dia(fecha: str, observaciones: str):
    try:
        with get_conn() as conn:
            prods = conn.execute("SELECT id, stock FROM productos").fetchall()
            for p in prods:
                conn.execute("INSERT OR REPLACE INTO snapshots_inventario (fecha, producto_id, stock_cierre) VALUES (?, ?, ?)",
                             (fecha, p["id"], p["stock"]))
            total_mov = conn.execute("SELECT COUNT(*) FROM movimientos WHERE date(fecha)=?", (fecha,)).fetchone()[0]
            conn.execute("INSERT INTO cierres_inventario (fecha, total_movimientos, total_productos, observaciones) VALUES (?, ?, ?, ?)",
                         (fecha, total_mov, len(prods), observaciones))
            conn.commit()
        return True, f"✅ Inventario del {fecha} cerrado"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def generar_hoja_impresion(fecha: str = None):
    fecha = fecha or date.today().isoformat()
    with get_conn() as conn:
        productos = [dict(r) for r in conn.execute("SELECT * FROM productos").fetchall()]
        snapshots = [dict(r) for r in conn.execute("SELECT * FROM snapshots_inventario WHERE fecha=?", (fecha,)).fetchall()]
        cierre = conn.execute("SELECT * FROM cierres_inventario WHERE fecha=?", (fecha,)).fetchone()
    return {"fecha": fecha, "productos": productos, "snapshot": snapshots, "cierre": dict(cierre) if cierre else None}