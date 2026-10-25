import requests
import pandas as pd
import time
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
        self.http = requests.Session()
        self._cache = {}
        self.timings = []

    def _request(self, method, path, **kwargs):
        require_identity()
        headers = {"apikey": self.key, "Content-Type": "application/json",
                   "Prefer": "return=representation"}
        # Las claves sb_secret_ no son JWT: el gateway las recibe en apikey.
        # La cabecera Bearer se conserva para service_role JWT de instalaciones anteriores.
        if not self.key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.key}"
        started = time.monotonic()
        try:
            r = self.http.request(method, f"{self.url}/rest/v1/{path}",
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
            if path == "rpc/bodega_registrar_venta_pagada" and r.status_code == 404:
                raise DataError("Ejecuta database/05_confirmacion_pago.sql en Supabase para activar la confirmación del pago.")
            if path in {"rpc/bodega_registrar_venta_caja", "rpc/bodega_buscar_ventas", "rpc/bodega_ticket_venta"} and r.status_code == 404:
                raise DataError("Ejecuta database/06_clientes_historial_ticket.sql en Supabase para activar clientes, historial y tickets.")
            if r.status_code==404 and any(path.startswith('rpc/'+prefix) for prefix in ('bodega_configurar_fiado','bodega_vender_fiado','bodega_abonar_fiado','bodega_anular_abono','bodega_consultar_fiado','bodega_resumen_fiado')):
                raise DataError('Ejecuta database/08_fiado.sql en Supabase para activar las cuentas de fiado.')
            if r.status_code==404 and any(path.startswith('rpc/'+prefix) for prefix in ('bodega_abrir_cobro','bodega_estado_cobro','bodega_finalizar_cobro','bodega_consultar_avisos','bodega_vincular_receptor','bodega_revocar_receptor')):
                raise DataError('Ejecuta las migraciones 07 y 09 y despliega recibir-aviso-yape para activar la espera de pago.')
            if path == "rpc/bodega_guardar_producto_catalogo" and r.status_code == 404:
                raise DataError("Ejecuta database/03_catalogo_visual.sql en Supabase para guardar las fotos y fichas del catálogo.")
            try:
                msg = r.json().get("message", "")
            except ValueError:
                msg = ""
            # No devolver respuestas arbitrarias ni claves/URLs en pantalla.
            known = ("Stock insuficiente", "Producto inactivo", "Cantidad inválida", "Operación reutilizada",
                     "Lote ya procesado", "Código desconocido", "Ticket histórico ya existe",
                     "Lote no válido", "Precio inválido", "No hay cambios", "Motivo requerido",
                     "El total cambió. Revisa el carrito y confirma el pago nuevamente",
                     "Confirma el pago completo antes de registrar la venta", "Importe de pago confirmado inválido",
                     "Datos del cliente inválidos", "Referencia de pago requerida", "Referencia de pago ya utilizada",
                     "Datos de caja cambiaron", "Venta no encontrada", "Filtros de ventas inválidos",
                     'Datos de cuenta de fiado inválidos','Cuenta de fiado no encontrada','Cuenta de fiado bloqueada',
                     'Fecha de fiado inválida','Límite de fiado insuficiente','El cliente tiene fiado vencido',
                     'Abono de fiado inválido','El abono supera la deuda pendiente','La venta está anulada',
                     'Anula primero los abonos del fiado y concilia la devolución','Abono no encontrado',
                     'El receptor ya tiene un cobro pendiente','Receptor no autorizado','Cobro no encontrado',
                     'El cobro requiere revisión','Comprueba el abono antes de registrar','La venta ya fue registrada')
            friendly = next((m for m in known if m in msg), None)
            raise DataError(friendly or f"Supabase rechazó la operación ({r.status_code}). Revisa esquema, permisos y formato.", confirmed_rejected=r.status_code<500)
        self.timings.append({"operacion": method+" "+path, "ms": round((time.monotonic()-started)*1000,1)})
        self.timings = self.timings[-40:]
        return r.json() if r.content else None

    def clear_cache(self):
        self._cache.clear()

    def table(self, name, *, since=None, until=None):
        require_identity()
        allowed = {"bodega_productos", "bodega_categorias", "bodega_proveedores", "bodega_v_ventas",
                   "bodega_ventas", "bodega_movimientos", "bodega_lotes", "bodega_predicciones", "bodega_eventos", "bodega_reposiciones", "bodega_tiempo", "bodega_v_cubo_ventas"}
        if name not in allowed:
            raise DataError("Tabla no permitida.")
        cache_key=(name,str(since),str(until))
        ttl=300 if name in {"bodega_categorias","bodega_proveedores"} else 15
        cached=self._cache.get(cache_key)
        if cached and time.monotonic()-cached[0] < ttl:
            return cached[1].copy(deep=True)
        # Paginar; no asumir que Supabase devuelve más de 1000 filas por petición.
        rows, offset = [], 0
        order = "id_detalle" if name == "bodega_v_ventas" else ("fecha" if name == "bodega_tiempo" else "id")
        while True:
            params={"select": self._select(name), "order": order, "limit":500, "offset":offset}
            bounds=[]
            if since: bounds.append(f"fecha.gte.{since}")
            if until: bounds.append(f"fecha.lte.{until}")
            if bounds: params["and"]="("+",".join(bounds)+")"
            page = self._request("GET", name, params=params)
            rows.extend(page)
            if not page:
                break
            offset += len(page)
        data=pd.DataFrame(rows)
        if len(self._cache)>=12: self._cache.pop(next(iter(self._cache)))
        self._cache[cache_key]=(time.monotonic(),data)
        return data.copy(deep=True)

    @staticmethod
    def _select(name):
        # Las pantallas generales de BI/actividad no exponen datos personales.
        if name=="bodega_ventas":
            return "id,fecha_hora,fecha,medio_pago,origen,ticket_externo,lote_id,usuario_uid,estado,total,pago_confirmado_en,pago_confirmado_por,pago_confirmado_total"
        return "*"

    def recent_table(self, name, limit=250):
        if name not in {"bodega_ventas","bodega_movimientos","bodega_lotes","bodega_predicciones","bodega_reposiciones","bodega_eventos"}:
            raise DataError("Tabla no permitida.")
        limit=max(1,min(int(limit),500))
        order="creado_en.desc,id.desc" if name in {"bodega_lotes","bodega_predicciones"} else "fecha_hora.desc,id.desc"
        return pd.DataFrame(self._request("GET",name,params={"select":self._select(name),"order":order,"limit":limit}))

    def rpc(self, name, payload, roles=("administrador",)):
        identity = require_role(*roles)
        payload = {**payload, "p_usuario": identity["uid"]}
        self.clear_cache()
        result=self._request("POST", f"rpc/{name}", json=payload)
        self.clear_cache()
        return result

    def sale(self, op, items, payment, *, confirmed_total=None, customer=None, reference="", entity=""):
        from bodega.payments import confirmed_amount
        from bodega.checkout import customer_data,payment_data
        amount = confirmed_amount(confirmed_total)
        customer=customer_data(customer); details=payment_data(payment,reference,entity)
        return self.rpc("bodega_registrar_venta_caja", {"p_operacion": op, "p_items": items,
            "p_pago": payment, "p_pago_confirmado": True, "p_total_confirmado": str(amount),
            "p_cliente":customer,"p_referencia":details["reference"],"p_entidad":details["entity"]},
            ("administrador", "cajero"))

    def search_sales(self, since, until, query="", status="TODOS", payment="Todos", page=0, size=25):
        require_role("administrador","cajero")
        identity=require_identity()
        return self._request("POST","rpc/bodega_buscar_ventas",json={
            "p_desde":str(since),"p_hasta":str(until),"p_busqueda":query,"p_estado":status,
            "p_pago":payment,"p_pagina":int(page),"p_tamano":int(size),"p_usuario":identity["uid"]})

    def receipt(self, vid):
        identity=require_role("administrador","cajero")
        return self._request("POST","rpc/bodega_ticket_venta",json={"p_venta":int(vid),"p_usuario":identity["uid"]})

    def credit_overview(self, query='', account=None):
        identity=require_role('administrador','cajero')
        return self._request('POST','rpc/bodega_consultar_fiado',json={'p_busqueda':str(query)[:120],
            'p_cuenta':int(account) if account is not None else None,'p_usuario':identity['uid']})

    def credit_summary(self, since, until):
        identity=require_role('administrador','cajero','analista')
        return self._request('POST','rpc/bodega_resumen_fiado',json={'p_desde':str(since),'p_hasta':str(until),'p_usuario':identity['uid']})

    def configure_credit(self, dni, name, limit, active):
        return self.rpc('bodega_configurar_fiado',{'p_dni':dni,'p_nombre':name,'p_limite':str(limit),'p_activo':active})

    def credit_sale(self, op, items, account, due, total):
        return self.rpc('bodega_vender_fiado',{'p_operacion':op,'p_items':items,'p_cuenta':int(account),
            'p_vencimiento':str(due),'p_total_confirmado':str(total)},('administrador','cajero'))

    def credit_payment(self, op, sale, amount, payment, reference='', entity=''):
        from bodega.checkout import payment_data
        from bodega.payments import confirmed_amount
        details=payment_data(payment,reference,entity);amount=confirmed_amount(amount)
        return self.rpc('bodega_abonar_fiado',{'p_id':op,'p_venta':int(sale),'p_importe':str(amount),
            'p_pago':payment,'p_referencia':details['reference'],'p_entidad':details['entity'],'p_confirmado':True},('administrador','cajero'))

    def reverse_credit_payment(self, payment, reason):
        return self.rpc('bodega_anular_abono',{'p_id':str(payment),'p_motivo':reason})

    def receivers(self):
        identity=require_role('administrador','cajero')
        return self._request('POST','rpc/bodega_consultar_avisos',json={'p_usuario':identity['uid']})['dispositivos']

    def pair_receiver(self, device, name, token_hash):
        return self.rpc('bodega_vincular_receptor',{'p_id':device,'p_nombre':name,'p_token_hash':token_hash})

    def revoke_receiver(self, device):
        return self.rpc('bodega_revocar_receptor',{'p_id':device})

    def start_charge(self, op, device, items, customer, total):
        return self.rpc('bodega_abrir_cobro',{'p_id':op,'p_dispositivo':device,'p_items':items,'p_cliente':customer,
            'p_total':str(total)},('administrador','cajero'))

    def charge_status(self, op):
        identity=require_role('administrador','cajero')
        return self._request('POST','rpc/bodega_estado_cobro',json={'p_id':op,'p_usuario':identity['uid']})

    def finish_charge(self, op, *, cancel=False, reference='', entity='YAPE DEL NEGOCIO', reviewed=False):
        return self.rpc('bodega_finalizar_cobro',{'p_id':op,'p_accion':'CANCELAR' if cancel else 'REGISTRAR',
            'p_referencia':reference,'p_entidad':entity,'p_revisado':reviewed},('administrador','cajero'))

    def movement(self, op, product_id, kind, quantity, cost, reason):
        return self.rpc("bodega_registrar_movimiento", {"p_operacion": op, "p_producto": product_id,
            "p_tipo": kind, "p_cantidad": quantity, "p_costo": cost, "p_motivo": reason})

    def save_product(self, product):
        require_role("administrador")
        self.clear_cache()
        result=self._request("POST", "rpc/bodega_guardar_producto_galeria", json={"p_producto": product})
        self.clear_cache()
        return result

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
