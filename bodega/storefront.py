"""Catálogo y caja con presentación de tienda para uso interno."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4
import html
import pandas as pd
import streamlit as st
from bodega import cart as rules
from bodega.analytics import kpis
from bodega.repository import DataError
from bodega.ui import page_header, product_image, image_source, svg_uri, ROOT, status_badge
from bodega.media import product_urls
from bodega.telemetry import record
from bodega.payments import fingerprint
from bodega.staff import session_name, ROLE_LABELS

PAGES = ["Inicio", "Registrar venta", "Historial de ventas", "Fiados", "Inventario", "Resumen BI", "Reposición", "Pronóstico", "Importar historial", "Actividad y datos"]
NAV_LABELS = {"Inicio":"Inicio", "Registrar venta":"Tienda interna", "Inventario":"Inventario",
    "Resumen BI":"BI", "Reposición":"Reposición", "Pronóstico":"Pronóstico",
    "Importar historial":"Importar", "Actividad y datos":"Actividad", "Historial de ventas":"Ventas", "Fiados":"Fiados"}
PAYMENTS = ["Efectivo", "Yape", "Plin", "Tarjeta", "Transferencia"]


def soles(value):
    return f"S/ {float(value):,.2f}"


def _cart():
    return st.session_state.setdefault("cart", [])


def go_to(page):
    st.session_state["page"] = page


def open_checkout():
    st.session_state["page"] = "Registrar venta"
    st.session_state["shop_view"] = "carrito"


def open_catalog():
    st.session_state["page"] = "Registrar venta"
    st.session_state["shop_view"] = "catalogo"


def _editable(role):
    return role in {"administrador", "cajero"} and not any(k in st.session_state for k in ('pending_sale','pending_credit','active_charge'))


def _add(products, product_id, quantity, role, discount=0):
    if not _editable(role):
        raise DataError("Resuelve la venta pendiente antes de modificar el carrito.")
    rules.add_item(_cart(), products, int(product_id), int(quantity), discount)


def _delta(products, product_id, delta, role):
    try:
        if not _editable(role):
            raise DataError("El carrito está pendiente de confirmación.")
        item = next(x for x in _cart() if x["producto_id"] == product_id)
        rules.change_quantity(_cart(), products, product_id, item["cantidad"] + delta)
    except DataError as exc:
        st.session_state["cart_error"] = str(exc)


def _remove(product_id, role):
    if _editable(role):
        st.session_state["cart"] = [x for x in _cart() if x["producto_id"] != product_id]


def _set_discount(products, product_id, key, role):
    try:
        if _editable(role):
            rules.set_discount(_cart(), products, product_id, st.session_state[key])
    except DataError as exc:
        st.session_state["cart_error"] = str(exc)


def _show_error():
    if "cart_error" in st.session_state:
        st.error(st.session_state.pop("cart_error"))


def _stepper(products, line, role, prefix):
    pid = line["producto_id"]
    with st.container(key=f"cart_qty_{prefix}_{pid}"):
        minus, value, plus, remove = st.columns([1, 1.15, 1, 1], gap="small")
        minus.button("−", key=f"minus_{prefix}_{pid}", help="Restar una unidad",
            on_click=_delta, args=(products, pid, -1, role), disabled=not _editable(role))
        value.markdown(f'<div style="text-align:center;padding-top:5px;font-size:13px">{line["cantidad"]}</div>', unsafe_allow_html=True)
        plus.button("+", key=f"plus_{prefix}_{pid}", help="Agregar una unidad",
            on_click=_delta, args=(products, pid, 1, role), disabled=not _editable(role))
        remove.button("×", key=f"remove_{prefix}_{pid}", help="Quitar este artículo",
            on_click=_remove, args=(pid, role), disabled=not _editable(role))


def _summary(cart_lines):
    amount = rules.totals(cart_lines)
    st.markdown(f'<div class="summary-row"><span>Subtotal</span><span>{soles(amount["subtotal"])}</span></div>'
        f'<div class="summary-row"><span>Descuentos</span><span>− {soles(amount["descuento"])}</span></div>'
        f'<div class="summary-row total"><span>Total</span><span>{soles(amount["total"])}</span></div>', unsafe_allow_html=True)
    return amount


@st.dialog("Carrito de venta", width="small", position="right", on_dismiss="rerun")
def cart_drawer(products, role):
    _show_error()
    rows = rules.lines(_cart(), products)
    if not rows:
        st.info("Tu carrito está vacío.")
        if st.button("Explorar productos", type="primary", on_click=open_catalog, width="stretch"):
            st.rerun(scope="app")
        return
    st.caption(f'{sum(r["cantidad"] for r in rows)} unidades · {len(rows)} artículos')
    for line in rows:
        p = rules.product_row(products, line["producto_id"])
        a, b = st.columns([1, 2.8])
        with a:
            product_image(p, "cart-product-image")
        with b:
            st.markdown(f'<p class="cart-line-name">{html.escape(line["nombre"])}</p><p class="cart-line-price">{soles(line["precio"])} por unidad</p>', unsafe_allow_html=True)
            _stepper(products, line, role, "drawer")
        st.divider()
    _summary(rows)
    if st.button("Ver carrito y finalizar", type="primary", on_click=open_checkout, width="stretch"):
        st.rerun(scope="app")
    st.caption("La venta se registra al confirmar en caja.")


@st.dialog("Detalle del producto", width="large", on_dismiss="rerun")
def product_dialog(products, product_id, role, repo=None):
    p = rules.product_row(products, product_id)
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        urls=product_urls(p)
        selected=st.radio("Vista del producto",range(len(urls)),format_func=lambda i:f"Foto {i+1}",
            horizontal=True,key=f"detail_photo_{product_id}") if len(urls)>1 else 0
        product_image(p, "product-detail-image",selected)
    with right:
        st.markdown(f'<span class="eyebrow">{html.escape(str(p.categoria))}</span><h2 class="product-detail-title">{html.escape(str(p.nombre))}</h2>'
            f'<div class="product-code">CÓDIGO {html.escape(str(p.codigo))}</div><div class="detail-price">{soles(p.precio)}</div>'
            + status_badge(int(p.stock), int(p.stock_minimo)), unsafe_allow_html=True)
        st.caption(f"{int(p.stock)} unidades disponibles")
        qty = st.number_input("Cantidad", min_value=1, max_value=max(1, int(p.stock)), value=1, step=1, key=f"detail_qty_{product_id}")
        if st.button("Agregar al carrito", type="primary", width="stretch", key=f"detail_add_{product_id}",
                     disabled=int(p.stock) == 0 or not _editable(role)):
            _add(products, product_id, qty, role)
            if repo: record(repo,"carrito_agregado",str(product_id))
            st.session_state["flash"] = f"{p.nombre} agregado a la venta."
            st.rerun(scope="app")
        with st.expander("INFORMACIÓN DEL PRODUCTO", expanded=True):
            description = str(p.get("descripcion", "") or "").strip()
            st.markdown(f'<p class="detail-description">{html.escape(description or "Consulta el código, la categoría y la disponibilidad de este artículo antes de registrar la venta.")}</p>', unsafe_allow_html=True)
            specs = [("Categoría", p.categoria), ("Proveedor", p.proveedor),
                ("Marca", p.get("marca", "")), ("Presentación", p.get("presentacion", "")),
                ("Stock", f"{int(p.stock)} unidades"), ("Stock mínimo", f"{int(p.stock_minimo)} unidades")]
            content = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(str(v))}</dd>" for k, v in specs if str(v).strip())
            st.markdown('<dl class="detail-specs">' + content + '</dl>', unsafe_allow_html=True)


def topbar(products, role, app_mode, logout, repo=None):
    available = PAGES if role == "administrador" else [p for p in PAGES if p != "Importar historial" and (role == "cajero" or p not in {"Registrar venta","Historial de ventas","Fiados"})]
    with st.container(key="masthead"):
        brand, navigation, cart = st.columns([2.2, 7.5, 1.1], vertical_alignment="center", gap="small")
        brand.markdown('<div class="brand-lockup"><span class="brand-monogram">M</span><span><strong class="brand-name">BODEGA MARGA</strong><span class="brand-sub">TIENDA INTELIGENTE · BI</span></span></div>', unsafe_allow_html=True)
        with navigation:
            with st.container(key="topnav"):
                page = st.radio("Tu espacio", available, horizontal=True, key="page",
                    format_func=lambda p: NAV_LABELS[p], label_visibility="collapsed")
        with cart:
            with st.container(key="cart_header"):
                count = sum(x["cantidad"] for x in _cart())
                if st.button(f"Carrito · {count}", icon=":material/shopping_bag:", key="open_cart", help="Abrir carrito de venta", disabled=role not in {"administrador", "cajero"} or 'active_charge' in st.session_state):
                    cart_drawer(products, role)
    status, account = st.columns([8, 1.6], vertical_alignment="center")
    badge = '<span class="demo-label">DEMOSTRACIÓN · datos de ejemplo · cambios solo en esta sesión</span>' if app_mode == "demo" else '<span>Sistema interno · sesión verificada</span>'
    name = session_name()
    role_label = ROLE_LABELS.get(role, role)
    status.markdown(f'<div class="session-line">{badge}<span>{html.escape(name)} · {html.escape(role_label)}</span></div>', unsafe_allow_html=True)
    with account:
        with st.popover("Mi sesión", width="stretch"):
            st.write(name)
            st.caption(f"Rol: {role_label}")
            label = "Reiniciar demostración" if app_mode == "demo" else "Cerrar sesión"
            if st.button(label):
                logout()
                st.rerun()
            if repo is not None and st.button('Actualizar datos'):
                repo.clear_cache()
                st.rerun()
            if role=='administrador' and getattr(repo,'timings',None):
                with st.expander('Tiempo de consultas de esta sesión'):
                    st.dataframe(pd.DataFrame(repo.timings),hide_index=True,width='stretch')
    return page


def home_page(products, sales, role, chart, today):
    with st.container(key="home_hero"):
        left, right = st.columns([1.15, 1], vertical_alignment="center")
        with left:
            st.markdown('<div class="home-hero-copy"><span class="eyebrow">BODEGA MARGA · LOS OLIVOS</span><h1>Gestiona tu tienda<br>con datos claros.</h1><p>Registra ventas, revisa tus existencias y prepara la reposición desde un solo lugar.</p></div>', unsafe_allow_html=True)
            a, b = st.columns([1, 1.15])
            if role in {"administrador", "cajero"}:
                a.button("Registrar venta →", type="primary", on_click=open_catalog, width="stretch")
            b.button("Ver dashboard BI", on_click=go_to, args=("Resumen BI",), width="stretch")
        with right:
            st.markdown(f'<img class="hero-art" src="{svg_uri(ROOT/"assets/hero_tienda.svg")}" alt="Ilustración de la bodega Marga">', unsafe_allow_html=True)
    daily = sales.loc[sales.fecha == pd.Timestamp(today)]
    values = kpis(daily)
    active = products.loc[products.activo] if not products.empty else products
    low = active.loc[active.stock <= active.stock_minimo] if not active.empty else active
    a, b, c, d = st.columns(4)
    a.metric("Ventas de hoy", soles(values["ventas"]))
    b.metric("Tickets de hoy", values["tickets"])
    c.metric("Productos activos", len(active))
    d.metric("Artículos con stock bajo", len(low))
    st.caption(f"Día de operación en Lima: {today.strftime('%d/%m/%Y')}")
    st.markdown('<section class="section-intro"><h2>Tu operación, en un solo lugar</h2><p>Elige lo que necesitas revisar o registrar.</p></section>', unsafe_allow_html=True)
    modules = [("sale", "▦", "Tienda interna", "Explora el catálogo y prepara una venta con el medio de pago recibido.", "Explorar productos", open_catalog, ()),
        ("bi", "▥", "Inteligencia de negocios", "Consulta ventas, margen bruto y productos que más aportan al negocio.", "Abrir resumen BI", go_to, ("Resumen BI",)),
        ("replenish", "◇", "Reposición de productos", "Revisa qué comprar y registra el motivo de cada decisión.", "Ver reposición sugerida", go_to, ("Reposición",))]
    for col, (key, icon, title, text, label, action, args) in zip(st.columns(3, gap="medium"), modules):
        with col:
            with st.container(key="module_" + key):
                st.markdown(f'<article class="module-card"><span class="module-icon">{icon}</span><h3>{title}</h3><p>{text}</p></article>', unsafe_allow_html=True)
                st.button(label, on_click=action, args=args, disabled=key == "sale" and role not in {"administrador", "cajero"})
    st.subheader("El día a día de tu bodega")
    left, right = st.columns([1.5, 1])
    with left:
        st.markdown("**Ventas de los últimos siete días**")
        if sales.empty:
            st.info("Registra una venta para empezar a ver tus resultados.")
        else:
            import plotly.express as px
            start = pd.Timestamp(today) - pd.Timedelta(days=6)
            data = sales.loc[sales.fecha >= start].groupby("fecha").ingreso.sum().reindex(pd.date_range(start, today), fill_value=0).rename_axis("fecha").reset_index(name="ingreso")
            chart(px.bar(data, x="fecha", y="ingreso", color_discrete_sequence=["#88b49d"], labels={"fecha":"Día", "ingreso":"Ventas S/"}))
    with right:
        st.markdown("**Pendientes de revisar**")
        if low.empty:
            st.success("Las existencias están por encima de sus mínimos.")
        else:
            st.dataframe(low[["nombre", "stock", "stock_minimo"]], hide_index=True, width="stretch")
        st.button("Ir a inventario", on_click=go_to, args=("Inventario",))
    if not sales.empty:
        with st.expander("Últimas ventas registradas"):
            recent = sales.groupby(["venta_id", "fecha", "medio_pago", "origen"], as_index=False).agg(total=("ingreso", "sum"), unidades=("cantidad", "sum"))
            st.dataframe(recent.sort_values(["fecha", "venta_id"], ascending=False).head(10), hide_index=True, width="stretch")


def filter_catalog(products, query="", category="Todos los productos", price_range=None, in_stock=False, sort="Nombre A–Z", sales=None):
    if products.empty:
        return products
    data = products.loc[products.activo].copy()
    query = query.strip()
    if query:
        data = data.loc[data.nombre.str.contains(query, case=False, regex=False) | data.codigo.astype(str).str.contains(query, case=False, regex=False)]
    if category != "Todos los productos":
        data = data.loc[data.categoria == category]
    if price_range is not None:
        data = data.loc[data.precio.between(*price_range)]
    if in_stock:
        data = data.loc[data.stock > 0]
    if sort == "Precio de menor a mayor":
        return data.sort_values(["precio", "nombre"])
    if sort == "Precio de mayor a menor":
        return data.sort_values(["precio", "nombre"], ascending=[False, True])
    if sort == "Más vendidos" and sales is not None and not sales.empty:
        count = sales.groupby("producto_id").cantidad.sum()
        data["_vendidos"] = data.id.map(count).fillna(0)
        return data.sort_values(["_vendidos", "nombre"], ascending=[False, True])
    return data.sort_values("nombre")


def catalog_page(products, sales, role, repo=None):
    st.markdown(f'<section class="catalog-banner"><div><span class="eyebrow">INICIO / TIENDA INTERNA</span><h1>Catálogo de productos</h1><p>Encuentra un artículo, consulta su información y agrégalo a la venta.</p></div><img src="{svg_uri(ROOT/"assets/hero_tienda.svg")}" alt="Bodega Marga"></section>', unsafe_allow_html=True)
    filters, content = st.columns([1.05, 5], gap="large")
    with filters:
        with st.container(key="catalog_filters"):
            st.markdown("**Explorar por**")
            cats = ["Todos los productos"] + (sorted(products.categoria.unique()) if not products.empty else [])
            category = st.radio("Categoría", cats, label_visibility="collapsed", key="catalog_category")
            st.divider()
            st.markdown("**Filtrar por**")
            max_price = max(1.0, float(products.precio.max())) if not products.empty else 1.0
            prices = st.slider("Precio (S/)", min_value=0.0, max_value=max_price, value=(0.0, max_price), step=.1, key="catalog_price")
            in_stock = st.checkbox("Con existencias", key="catalog_stock")
            st.caption("El stock y los precios corresponden al catálogo actual.")
    with content:
        a, b = st.columns([2.5, 1.4])
        query = a.text_input("Buscar producto o código", placeholder="Escribe un nombre o escanea un código…", key="catalog_search")
        sort = b.selectbox("Ordenar por", ["Nombre A–Z", "Precio de menor a mayor", "Precio de mayor a menor", "Más vendidos"], key="catalog_sort")
        result = filter_catalog(products, query, category, prices, in_stock, sort, sales)
        st.markdown(f'<div class="catalog-heading"><h2>{html.escape(category)}</h2><span class="catalog-count">{len(result)} productos</span></div>', unsafe_allow_html=True)
        if result.empty:
            st.info("No hay productos para esos filtros.")
            return
        count = min(st.session_state.get("catalog_limit", 12), len(result))
        records = result.head(count).to_dict("records")
        for offset in range(0, len(records), 4):
            with st.container(key=f"product_grid_{offset}"):
                for col, product in zip(st.columns(4, gap="small"), records[offset:offset + 4]):
                    pid = int(product["id"])
                    with col:
                        with st.container(key=f"product_card_{pid}"):
                            product_image(product)
                            st.markdown(status_badge(int(product["stock"]), int(product["stock_minimo"])) +
                                f'<p class="product-card-name">{html.escape(product["nombre"])}</p><p class="product-card-price">{soles(product["precio"])}</p>'
                                f'<p class="product-code">{int(product["stock"])} unidades disponibles</p>', unsafe_allow_html=True)
                            if st.button("Ver producto", key=f"detail_{pid}", width="stretch"):
                                if repo:record(repo,"producto_visto",str(pid))
                                product_dialog(products, pid, role, repo)
                            if st.button("Agregar al carrito", key=f"add_{pid}", width="stretch", type="primary", disabled=int(product["stock"]) == 0 or not _editable(role)):
                                _add(products, pid, 1, role)
                                if repo:record(repo,"carrito_agregado",str(pid))
                                st.session_state["flash"] = f'{product["nombre"]} agregado a la venta.'
                                st.rerun()
        if count < len(result) and st.button("Cargar más productos", width="stretch"):
            st.session_state["catalog_limit"] = count + 12
            st.rerun()


def _confirm(repo, payment, products, finish, notify):
    if "pending_sale" not in st.session_state:
        rows = rules.lines(_cart(), products)
        if not rows or any(not x["activo"] or x["cantidad"] > x["stock"] for x in rows):
            raise DataError("Revisa la disponibilidad de los artículos antes de cobrar.")
        context=st.session_state.get('checkout_context',{'customer':{},'reference':'','entity':''})
        if not st.session_state.get("payment_received") or st.session_state.get("checkout_fingerprint") != fingerprint(rows, payment,**context):
            raise DataError("Confirma que recibiste el pago completo antes de registrar la venta.")
        st.session_state["pending_sale"] = {"op": str(uuid4()), "items": [dict(x) for x in _cart()],
            "payment": payment, "confirmed_total": rules.totals(rows)["total"],**context}
    pending = st.session_state["pending_sale"]
    result = repo.sale(pending["op"], pending["items"], pending["payment"], confirmed_total=pending.get("confirmed_total"),
        customer=pending.get('customer'),reference=pending.get('reference',''),entity=pending.get('entity',''))
    st.session_state["last_sale_receipt"] = {"venta_id": result["venta_id"], "total": float(result["total"]), "payment": pending["payment"], 'orden':result.get('orden',str(result['venta_id']))}
    del st.session_state["pending_sale"]
    st.session_state["cart"] = []
    st.session_state["reset_payment_confirmation"] = True
    notify(repo, "venta_confirmada")
    finish(f'Venta {result["venta_id"]} confirmada · {soles(result["total"])}')


def checkout_page(repo, products, role, finish, notify):
    page_header("Mi carrito", "Revisa los artículos, recibe el pago y confirma la venta.")
    from bodega import credit,charge_wait
    if credit.pending_checkout(repo,finish,notify) or charge_wait.active(repo):return
    st.button("← Seguir agregando productos", on_click=open_catalog)
    receipt = st.session_state.get("last_sale_receipt")
    if receipt and not _cart():
        st.markdown(f'<section class="receipt"><strong>Venta {receipt["venta_id"]} registrada</strong><p>{soles(receipt["total"])} · {html.escape(receipt["payment"])} · Consulta el resultado en BI o en actividad.</p></section>', unsafe_allow_html=True)
        from bodega.receipts import receipt_panel
        receipt_panel(repo,receipt['venta_id'])
    if "pending_sale" in st.session_state:
        pending = st.session_state["pending_sale"]
        st.warning("La venta está pendiente de confirmación. Reintenta con los mismos datos para evitar duplicarla.")
        st.dataframe(pd.DataFrame(pending["items"]), hide_index=True, width="stretch")
        st.caption(f'Pago confirmado en caja: {pending["payment"]} · {soles(pending.get("confirmed_total", 0))}. No vuelvas a cobrar al cliente.')
        if st.button("Reintentar venta pendiente", type="primary"):
            _confirm(repo, pending["payment"], products, finish, notify)
        return
    _show_error()
    rows = rules.lines(_cart(), products)
    if not rows:
        st.info("Tu carrito está vacío. Elige productos para registrar la siguiente venta.")
        return
    left, right = st.columns([1.8, 1], gap="large")
    with left:
        st.subheader('Cliente de la venta')
        a,b=st.columns([1,2])
        dni=a.text_input('DNI del cliente (opcional)',max_chars=8,key='sale_customer_dni')
        name=b.text_input('Nombre del cliente (opcional)',max_chars=120,key='sale_customer_name')
        st.caption('Puedes vender a Consumidor final dejando ambos campos vacíos. Si registras DNI, completa también el nombre.')
        from bodega.checkout import customer_data,payment_data
        customer={'dni':dni,'nombre':name}; customer_valid=True
        try: customer=customer_data(customer)
        except DataError as exc: st.error(str(exc));customer_valid=False
        st.subheader("Artículos de la venta")
        for line in rows:
            product = rules.product_row(products, line["producto_id"])
            a, b, c = st.columns([.9, 2.4, 1.1], vertical_alignment="center")
            with a:
                product_image(product, "cart-product-image")
            with b:
                st.markdown(f'<p class="cart-line-name">{html.escape(line["nombre"])}</p><p class="cart-line-price">{soles(line["precio"])} por unidad · {html.escape(str(line["codigo"]))}</p>', unsafe_allow_html=True)
                _stepper(products, line, role, "checkout")
            c.markdown(f'**{soles(line["total"])}**')
            if not line["activo"] or line["cantidad"] > line["stock"]:
                st.error("Revisa este artículo: cambió su disponibilidad.")
            with st.expander("Descuento de esta línea"):
                key = f'discount_{line["producto_id"]}'
                st.number_input("Descuento S/", min_value=0.0, max_value=float(line["subtotal"]),
                    value=float(line["descuento"]), step=.1, key=key, on_change=_set_discount,
                    args=(products, line["producto_id"], key, role))
            st.divider()
        if st.button("Vaciar carrito", key="clear_cart"):
            st.session_state["cart"] = []
            st.rerun()
    with right:
        with st.container(key="order_summary"):
            st.subheader("Resumen de la venta")
            amount = _summary(rows)
            st.markdown('<p class="checkout-label">Medio de pago recibido</p>', unsafe_allow_html=True)
            with st.container(key="payment_methods"):
                payment = st.radio("Medio de pago", PAYMENTS+(['Fiado'] if credit.enabled() else []), horizontal=True, label_visibility="collapsed", key="sale_payment")
            if st.session_state.get('checkout_payment_method')!=payment:
                st.session_state['payment_reference']=''
                st.session_state['payment_received']=False
                st.session_state['checkout_payment_method']=payment
            if payment=='Fiado':
                if customer_valid:credit.checkout(repo,rows,amount['total'],customer,_cart(),finish,notify)
                return
            reference=entity='';payment_valid=True
            if payment!='Efectivo':
                defaults={'Yape':'Yape del negocio','Plin':'Plin del negocio','Tarjeta':'POS del negocio','Transferencia':'BCP'}
                entity=st.text_input('Entidad o cuenta receptora',value=defaults[payment],max_chars=60,key=f'payment_entity_{payment}')
                reference=st.text_input('Código de operación del pago',max_chars=100,key='payment_reference',
                    help='Referencia del abono o código de aprobación del POS. No ingreses el número de tarjeta.')
                try:
                    details=payment_data(payment,reference,entity)
                    reference,entity=details['reference'],details['entity']
                except DataError:
                    payment_valid=False
                    st.caption('Completa una referencia válida de al menos 4 caracteres para identificar el pago.')
            context={'customer':customer,'reference':reference,'entity':entity}
            st.session_state['checkout_context']=context
            current = fingerprint(rows, payment,**context)
            if st.session_state.pop("reset_payment_confirmation", False) or st.session_state.get("checkout_fingerprint") != current:
                st.session_state["payment_received"] = False
            st.session_state["checkout_fingerprint"] = current
            valid = customer_valid and payment_valid and all(x["activo"] and x["cantidad"] <= x["stock"] for x in rows)
            instructions = {"Efectivo": "Cuenta el efectivo recibido y entrega el vuelto que corresponda.",
                "Yape": "Comprueba el ingreso en el Yape del negocio antes de confirmar.",
                "Plin": "Comprueba el ingreso en el Plin del negocio antes de confirmar.",
                "Tarjeta": "Comprueba que el POS indique pago aprobado por el importe completo.",
                "Transferencia": "Comprueba el abono en la cuenta del negocio antes de confirmar."}
            st.caption(instructions[payment])
            if payment=='Yape':charge_wait.checkout(repo,_cart(),customer,amount['total'],customer_valid and all(x['activo'] and x['cantidad']<=x['stock'] for x in rows))
            received = st.checkbox(f'Confirmo que recibí {soles(amount["total"])} por {payment}',
                key="payment_received", disabled=not valid)
            if st.button("Confirmar venta", type="primary", width="stretch", disabled=not received or not valid):
                _confirm(repo, payment, products, finish, notify)
            st.caption("Verificación manual del cajero. La aplicación no consulta el estado del pago en bancos o billeteras.")
            st.caption("Al confirmar se guarda la orden y su ticket interno PDF. La boleta electrónica SUNAT requiere habilitar emisión tributaria.")


def sale_page(repo, products, role, finish, notify, sales):
    if role not in {"administrador", "cajero"}:
        st.info("El registro de ventas corresponde a caja o administración.")
        return
    if st.session_state.get("shop_view") == "carrito" or "pending_sale" in st.session_state:
        checkout_page(repo, products, role, finish, notify)
    else:
        catalog_page(products, sales, role, repo)
