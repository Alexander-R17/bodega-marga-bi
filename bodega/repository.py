import requests
import pandas as pd
from bodega.config import setting
from bodega.auth import require_identity, require_role


class DataError(Exception):
    def __init__(self, message, confirmed_rejected=True):
        super().__init__(message)
        self.confirmed_rejected = confirmed_rejected


class CloudRepository:
    def __init__(self):
        self.url = str(setting("SUPABASE_URL")).strip().rstrip("/")
        self.key = str(setting("SUPABASE_SERVICE_ROLE_KEY")).strip()
        if not self.url.startswith("https://") or not self.key:
            raise DataError("Configura SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en Secrets.")
        if self.key.startswith("sb_publishable_"):
            raise DataError("La conexión necesita una clave secreta de Supabase (sb_secret_...) o legacy service_role. Sustituye la clave pública en SUPABASE_SERVICE_ROLE_KEY dentro de Secrets.")
        if any(char.isspace() for char in self.key):
            raise DataError("Copia la clave de Supabase completa en una sola línea, sin espacios, dentro de SUPABASE_SERVICE_ROLE_KEY.")

    def _request(self, method, path, **kwargs):
        require_identity()
        headers = {"apikey": self.key, "Content-Type": "application/json",
                   "Prefer": "return=representation"}
        # Las claves sb_secret_ no son JWT: el gateway las recibe en apikey.
        # La cabecera Bearer se conserva para service_role JWT de instalaciones anteriores.
        if not self.key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.key}"
        try:
            r = requests.request(method, f"{self.url}/rest/v1/{path}",
                                 headers=headers, timeout=40, **kwargs)
        except requests.RequestException:
            raise DataError("No se recibió confirmación de Supabase. Reintenta la misma operación; conserva su identificador.", confirmed_rejected=False) from None
        if not r.ok:
            if r.status_code == 401:
                raise DataError("Supabase no autorizó el acceso (401). Comprueba en Secrets que SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY sean del mismo proyecto. Usa una clave secreta sb_secret_... o legacy service_role, vigente y completa; las claves anon y sb_publishable_... no dan acceso a esta aplicación.")
            if r.status_code == 403:
                raise DataError("Supabase denegó el acceso (403). Comprueba la clave privada del proyecto y los permisos de service_role sobre las tablas bodega_* y sus funciones.")
            if path == "rpc/bodega_guardar_producto_galeria" and r.status_code == 404:
                raise DataError("Ejecuta database/04_galeria_y_bi.sql en Supabase para guardar varias imágenes.")
            if path == "rpc/bodega_guardar_producto_catalogo" and r.status_code == 404:
                raise DataError("Ejecuta database/03_catalogo_visual.sql en Supabase para guardar las fotos y fichas del catálogo.")
            try:
                msg = r.json().get("message", "")
            except ValueError:
                msg = ""
            # No devolver respuestas arbitrarias ni claves/URLs en pantalla.
            known = ("Stock insuficiente", "Producto inactivo", "Cantidad inválida", "Operación reutilizada",
                     "Lote ya procesado", "Código desconocido", "Ticket histórico ya existe",
                     "Lote no válido", "Precio inválido", "No hay cambios", "Motivo requerido")
            friendly = next((m for m in known if m in msg), None)
            raise DataError(friendly or f"Supabase rechazó la operación ({r.status_code}). Revisa esquema, permisos y formato.", confirmed_rejected=r.status_code<500)
        return r.json() if r.content else None

    def table(self, name):
        allowed = {"bodega_productos", "bodega_categorias", "bodega_proveedores", "bodega_v_ventas",
                   "bodega_ventas", "bodega_movimientos", "bodega_lotes", "bodega_predicciones", "bodega_eventos", "bodega_reposiciones", "bodega_tiempo", "bodega_v_cubo_ventas"}
        if name not in allowed:
            raise DataError("Tabla no permitida.")
        # Paginar; no asumir que Supabase devuelve más de 1000 filas por petición.
        rows, offset = [], 0
        order = "id_detalle" if name == "bodega_v_ventas" else ("fecha" if name == "bodega_tiempo" else "id")
        while True:
            page = self._request("GET", name, params={"select": "*", "order": order,
                                                     "limit": 500, "offset": offset})
            rows.extend(page)
            if not page:
                break
            offset += len(page)
        return pd.DataFrame(rows)

    def rpc(self, name, payload, roles=("administrador",)):
        identity = require_role(*roles)
        payload = {**payload, "p_usuario": identity["uid"]}
        return self._request("POST", f"rpc/{name}", json=payload)

    def sale(self, op, items, payment):
        return self.rpc("bodega_registrar_venta", {"p_operacion": op, "p_items": items,
                                                  "p_pago": payment}, ("administrador", "cajero"))

    def movement(self, op, product_id, kind, quantity, cost, reason):
        return self.rpc("bodega_registrar_movimiento", {"p_operacion": op, "p_producto": product_id,
            "p_tipo": kind, "p_cantidad": quantity, "p_costo": cost, "p_motivo": reason})

    def save_product(self, product):
        require_role("administrador")
        return self._request("POST", "rpc/bodega_guardar_producto_galeria", json={"p_producto": product})

    def create_batch(self, batch_id, name, sha, records):
        return self.rpc("bodega_crear_lote", {"p_id": batch_id, "p_nombre": name,
            "p_hash": sha, "p_filas": records})

    def process_batch(self, batch_id):
        return self.rpc("bodega_procesar_lote", {"p_lote": batch_id})

    def save_forecast(self, records):
        return self.rpc("bodega_guardar_predicciones", {"p_filas": records}, ("administrador", "analista"))

    def annul(self, op, vid, reason):
        return self.rpc("bodega_anular_venta", {"p_operacion":op,"p_venta":vid,"p_motivo":reason})

    def decision(self, op, product_id, units, decision, reason, context):
        return self.rpc("bodega_decidir_reposicion", {"p_id":op,"p_producto":product_id,
            "p_unidades":units,"p_decision":decision,"p_motivo":reason,"p_contexto":context})

    def event(self, event, detail="", session_id=None, page=""):
        identity = require_identity()
        return self._request("POST", "bodega_eventos", json={"usuario_uid": identity["uid"],
            "evento": event, "detalle": detail[:120], "sesion_id": session_id, "pagina": page[:100]})
