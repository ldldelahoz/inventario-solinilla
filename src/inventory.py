from src.db import get_conn

def obtener_productos():
    """Obtiene todos los productos."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre, stock, fecha_vencimiento FROM productos ORDER BY nombre")
            return [dict(row) for row in cur.fetchall()]

def crear_producto(id_prod: str, nombre: str, fecha_vencimiento: str = None):
    """Crea un nuevo producto."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO productos (id, nombre, stock, fecha_vencimiento) 
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (id_prod, nombre, 0, fecha_vencimiento))
                conn.commit()
            if cur.rowcount == 0:
                return False, "El producto ya existe"
        return True, "✅ Producto creado"
    except Exception as e:
        return False, f"❌ Error: {e}"

def registrar_movimiento(id_prod: str, tipo: str, cantidad: float, motivo: str = None):
    """Registra un movimiento de inventario."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Registrar el movimiento
                cur.execute("""
                    INSERT INTO movimientos (producto_id, tipo, cantidad, motivo) 
                    VALUES (%s, %s, %s, %s)
                """, (id_prod, tipo, cantidad, motivo))
                
                # Actualizar stock del producto
                if tipo == "entrada":
                    cur.execute("UPDATE productos SET stock = stock + %s WHERE id = %s", (cantidad, id_prod))
                else:
                    cur.execute("UPDATE productos SET stock = stock - %s WHERE id = %s", (cantidad, id_prod))
                
                conn.commit()
        return True, "✅ Movimiento registrado"
    except Exception as e:
        return False, f"❌ Error: {e}"

def buscar_productos(query: str):
    """Busca productos por nombre o ID."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, nombre, stock, fecha_vencimiento 
                FROM productos 
                WHERE nombre ILIKE %s OR id ILIKE %s 
                ORDER BY nombre
            """, (f"%{query}%", f"%{query}%"))
            return [dict(row) for row in cur.fetchall()]

def obtener_movimientos_dia(fecha: str = None):
    """Obtiene movimientos de un día específico."""
    from datetime import date
    if not fecha:
        fecha = date.today().isoformat()
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT m.id, m.producto_id, p.nombre, m.tipo, m.cantidad, m.motivo, m.fecha
                FROM movimientos m
                JOIN productos p ON m.producto_id = p.id
                WHERE DATE(m.fecha) = %s
                ORDER BY m.fecha DESC
            """, (fecha,))
            return [dict(row) for row in cur.fetchall()]

def generar_reporte(fecha: str = None):
    """Genera un reporte de inventario."""
    from datetime import date
    if not fecha:
        fecha = date.today().isoformat()
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.id, p.nombre, p.stock, p.fecha_vencimiento,
                       COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.cantidad ELSE 0 END), 0) as total_entradas,
                       COALESCE(SUM(CASE WHEN m.tipo = 'salida' THEN m.cantidad ELSE 0 END), 0) as total_salidas
                FROM productos p
                LEFT JOIN movimientos m ON p.id = m.producto_id AND DATE(m.fecha) = %s
                GROUP BY p.id, p.nombre, p.stock, p.fecha_vencimiento
                ORDER BY p.nombre
            """, (fecha,))
            return [dict(row) for row in cur.fetchall()]

def editar_movimiento(mov_id: int, cantidad: float, motivo: str = None):
    """Edita un movimiento existente."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Obtener el movimiento original para ajustar stock
                cur.execute("SELECT producto_id, tipo, cantidad FROM movimientos WHERE id = %s", (mov_id,))
                old = cur.fetchone()
                if not old:
                    return False, "Movimiento no encontrado"
                
                # Actualizar el movimiento
                cur.execute("""
                    UPDATE movimientos SET cantidad = %s, motivo = %s WHERE id = %s
                """, (cantidad, motivo, mov_id))
                
                # Ajustar stock: revertir el efecto antiguo y aplicar el nuevo
                diff = cantidad - old["cantidad"]
                if old["tipo"] == "entrada":
                    cur.execute("UPDATE productos SET stock = stock + %s WHERE id = %s", (diff, old["producto_id"]))
                else:
                    cur.execute("UPDATE productos SET stock = stock - %s WHERE id = %s", (diff, old["producto_id"]))
                
                conn.commit()
        return True, "✅ Movimiento actualizado"
    except Exception as e:
        return False, f"❌ Error: {e}"

def eliminar_movimiento(mov_id: int):
    """Elimina un movimiento y ajusta el stock."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Obtener datos del movimiento antes de borrar
                cur.execute("SELECT producto_id, tipo, cantidad FROM movimientos WHERE id = %s", (mov_id,))
                mov = cur.fetchone()
                if not mov:
                    return False, "Movimiento no encontrado"
                
                # Revertir el efecto en el stock
                if mov["tipo"] == "entrada":
                    cur.execute("UPDATE productos SET stock = stock - %s WHERE id = %s", (mov["cantidad"], mov["producto_id"]))
                else:
                    cur.execute("UPDATE productos SET stock = stock + %s WHERE id = %s", (mov["cantidad"], mov["producto_id"]))
                
                # Eliminar el movimiento
                cur.execute("DELETE FROM movimientos WHERE id = %s", (mov_id,))
                conn.commit()
        return True, "✅ Movimiento eliminado"
    except Exception as e:
        return False, f"❌ Error: {e}"

def cerrar_inventario_dia(fecha: str = None, observaciones: str = ""):
    """Cierra el inventario de un día creando un snapshot."""
    from datetime import date
    if not fecha:
        fecha = date.today().isoformat()
    
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Obtener productos con su stock actual
                cur.execute("SELECT id, stock FROM productos")
                productos = cur.fetchall()
                
                # Crear snapshot para cada producto
                for prod in productos:
                    cur.execute("""
                        INSERT INTO snapshots_inventario (fecha, producto_id, stock_cierre) 
                        VALUES (%s, %s, %s)
                        ON CONFLICT (fecha, producto_id) DO UPDATE SET stock_cierre = EXCLUDED.stock_cierre
                    """, (fecha, prod["id"], prod["stock"]))
                
                # Registrar el cierre
                cur.execute("""
                    INSERT INTO cierres_inventario (fecha, total_productos, observaciones) 
                    VALUES (%s, %s, %s)
                """, (fecha, len(productos), observaciones))
                
                conn.commit()
        return True, "✅ Inventario cerrado"
    except Exception as e:
        return False, f"❌ Error: {e}"

def generar_hoja_impresion(fecha: str = None):
    """Genera datos para hoja de inventario imprimible."""
    from datetime import date
    if not fecha:
        fecha = date.today().isoformat()
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.id, p.nombre, p.stock, p.fecha_vencimiento,
                       COALESCE(s.stock_cierre, p.stock) as stock_cierre_anterior
                FROM productos p
                LEFT JOIN snapshots_inventario s ON p.id = s.producto_id AND s.fecha = %s
                ORDER BY p.nombre
            """, (fecha,))
            def eliminar_producto(id_prod: str):
                """Elimina un producto de la base de datos."""
                try:
                    with get_conn() as conn:
                        with conn.cursor() as cur:
                            cur.execute("DELETE FROM productos WHERE id = %s", (id_prod,))
                            conn.commit()
                            if cur.rowcount > 0:
                                return True, "✅ Producto eliminado"
                            else:
                                return False, "❌ Producto no encontrado"
                except Exception as e:
                    return False, f"❌ Error: {e}"
            return [dict(row) for row in cur.fetchall()]
        
def eliminar_producto(id_prod: str):
    """Elimina un producto de la base de datos."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM productos WHERE id = %s", (id_prod,))
                conn.commit()
                if cur.rowcount > 0:
                    return True, "✅ Producto eliminado"
                return False, "❌ Producto no encontrado"
    except Exception as e:
        return False, f"❌ Error al eliminar: {e}"