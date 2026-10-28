from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4
from pathlib import Path
import html
import pandas as pd
import plotly.express as px
import streamlit as st

from bodega.config import mode
from bodega.auth import AccessError, login, require_identity, logout, send_verification, identity_scope
from bodega.repository import CloudRepository, DataError
from bodega.demo import DemoRepository
from bodega.imports import validate_csv, COLUMNS
from bodega.analytics import prepare_sales, enrich_products, kpis, replenish, daily_series, forecast, csv_export
from bodega import storefront
from bodega.ui import inject_css, page_header, footer, valid_image_url
from bodega.media import product_urls, normalize_urls, MAX_IMAGES
from bodega.telemetry import record
from bodega.staff import present_activity, team_editor

st.set_page_config(page_title="Bodega Marga · Tienda interna y BI", page_icon="🛒", layout="wide", initial_sidebar_state="collapsed")
inject_css()

ROOT = Path(__file__).resolve().parent
TODAY = datetime.now(ZoneInfo("America/Lima")).date()
PAGES = storefront.PAGES


def soles(value):
    return f"S/ {value:,.2f}"


def hero(title, text):
    page_header(title, text)


def chart(fig):
    fig.update_layout(font={"family":"Arial","color":"#173b32"},paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",margin={"t":30,"b":20,"l":20,"r":15},height=330)
    st.plotly_chart(fig,width="stretch")


def notify(repo,event,detail=""):
    # Telemetría de uso sin emails, nombres de clientes ni credenciales.
    try:
        record(repo,event,detail)
    except (DataError,AccessError):
        st.caption("La operación se confirmó; no se pudo registrar su evento de uso.")


def finish(message):
    st.session_state["flash"]=message
    st.rerun()


def export_button(df,filename,label="Descargar CSV"):
    st.download_button(label,csv_export(df),filename,"text/csv")


def go_to(page):
    st.session_state["page"]=page


def home_page(products, sales, role):
    storefront.home_page(products, sales, role, chart, TODAY)


def overview(repo,products,sales,role):
    from bodega.bi_pages import dashboard
    dashboard(repo,products,sales,role,TODAY,forecast_page)


def sale_page(repo, products, role, sales):
    storefront.sale_page(repo, products, role, finish, notify, sales)


def inventory_page(repo,products,role):
    hero("Inventario claro, atención rápida", "Revisa existencias y registra las entradas o diferencias de conteo.")
    if not products.empty:
        a,b,c=st.columns(3)
        active=products.loc[products.activo]
        a.metric("Artículos activos",len(active)); b.metric("Unidades disponibles",int(active.stock.sum()))
        c.metric("Valor a costo",soles(float((active.stock*active.costo).sum())))
        search=st.text_input("Buscar producto o código")
        view=products.loc[products.nombre.str.contains(search,case=False,regex=False) | products.codigo.str.contains(search,case=False,regex=False)]
        st.dataframe(view[["codigo","nombre","categoria","proveedor","precio","costo","stock","stock_minimo","plazo_dias","activo"]],hide_index=True,width="stretch")
        export_button(view,"inventario_bodega_marga.csv")
    if role!="administrador": return
    catalog,movement,annul=st.tabs(["Catálogo","Entradas y conteo","Anular venta"])
    with catalog:
        options=[None]+([] if products.empty else products.id.tolist())
        labels={} if products.empty else dict(zip(products.id,products.nombre))
        pid=st.selectbox("Artículo",options,format_func=lambda v:"Crear producto" if v is None else labels[v])
        p={} if pid is None else products.loc[products.id==pid].iloc[0].to_dict()
        saved_urls=product_urls(p)
        count_key=f"gallery_count_{pid}"
        image_count=st.session_state.setdefault(count_key,max(1,len(saved_urls)))
        with st.form("catalog_form",enter_to_submit=False):
            a,b=st.columns(2)
            code=a.text_input("Código / código de barras",value=p.get("codigo",""),max_chars=60)
            name=b.text_input("Nombre",value=p.get("nombre",""),max_chars=120)
            category=a.text_input("Categoría",value=p.get("categoria","Abarrotes"),max_chars=80)
            supplier=b.text_input("Proveedor",value=p.get("proveedor","Proveedor local"),max_chars=100)
            price=a.number_input("Precio de venta S/",min_value=0.0,value=float(p.get("precio",0)),step=.1)
            cost=b.number_input("Costo de referencia S/",min_value=0.0,value=float(p.get("costo",0)),step=.1)
            minimum=a.number_input("Stock mínimo",min_value=0,value=int(p.get("stock_minimo",5)),step=1)
            lead=b.number_input("Plazo del proveedor (días)",min_value=0,max_value=90,value=int(p.get("plazo_dias",2)),step=1)
            st.markdown("**Información del producto**")
            description=st.text_area("Descripción",value=p.get("descripcion", ""),max_chars=1500,height=100)
            brand=a.text_input("Marca",value=p.get("marca", ""),max_chars=80)
            presentation=b.text_input("Presentación",value=p.get("presentacion", ""),max_chars=120,placeholder="Ej. bolsa de 1 kg")
            st.markdown("**Imágenes referenciales por URL**")
            image_values=[st.text_input(f"URL HTTPS de imagen {i+1}",
                value=saved_urls[i] if i<len(saved_urls) else "",max_chars=2048,
                placeholder="https://...",key=f"gallery_url_{pid}_{i}") for i in range(image_count)]
            add_image=st.form_submit_button("Agregar otra URL de imagen referencial",disabled=image_count>=MAX_IMAGES)
            remove_image=st.form_submit_button("Quitar última URL",disabled=image_count<=1)
            st.caption("Hasta 8 URL. La primera es la portada; las demás cambian al pasar el cursor. Deja vacía una casilla para omitirla.")
            enabled=st.checkbox("Producto activo",value=bool(p.get("activo",True)))
            submit=st.form_submit_button("Guardar producto",type="primary")
        if add_image or remove_image:
            st.session_state[count_key]=image_count+(1 if add_image else -1)
            st.rerun()
        if submit:
            images=normalize_urls(image_values)
            if not all(x.strip() for x in [code,name,category,supplier]): st.error("Completa los campos de texto.")
            else:
                repo.save_product({"id":int(pid) if pid is not None else None,"codigo":code.strip(),"nombre":name.strip(),
                    "categoria":category.strip(),"proveedor":supplier.strip(),"precio":round(price,2),"costo":round(cost,2),
                    "stock_minimo":minimum,"plazo_dias":lead,"activo":enabled,
                    "descripcion":description.strip(),"marca":brand.strip(),"presentacion":presentation.strip(),
                    "imagen_url":images[0] if images else "","imagenes_urls":images})
                notify(repo,"producto_guardado"); finish("Producto guardado. Registra una entrada para cargar existencias.")
        st.caption("El catálogo nunca modifica stock. Las ventas conservan el precio y costo que tenían al registrarse.")
    with movement:
        if products.empty: st.info("Primero crea un producto.")
        elif "pending_movement" in st.session_state:
            pending=st.session_state.pending_movement
            st.warning("Movimiento pendiente de confirmación. Reintenta la misma operación.")
            if st.button("Reintentar movimiento"):
                result=repo.movement(**pending); del st.session_state["pending_movement"]
                finish(f'Movimiento confirmado. Stock: {result["stock"]}')
        else:
            with st.form("movement_form"):
                ids=products.id.tolist(); labels=dict(zip(products.id,products.nombre))
                pid=st.selectbox("Producto",ids,format_func=labels.get,key="movement_product")
                kind=st.selectbox("Operación",["ENTRADA","AJUSTE","MERMA"])
                qty=st.number_input("Unidades (en AJUSTE: stock físico total contado)",min_value=0,value=1,step=1)
                cost=st.number_input("Costo unitario de compra S/ (para ENTRADA)",min_value=0.0,value=1.0,step=.1)
                reason=st.text_input("Motivo o referencia",max_chars=200)
                submit=st.form_submit_button("Registrar movimiento",type="primary")
            if submit:
                if len(reason.strip())<3: st.error("Escribe el motivo o referencia.")
                else:
                    pending={"op":str(uuid4()),"product_id":int(pid),"kind":kind,"quantity":qty,"cost":round(cost,2),"reason":reason.strip()}
                    st.session_state["pending_movement"]=pending
                    result=repo.movement(**pending); del st.session_state["pending_movement"]
                    notify(repo,"movimiento_confirmado"); finish(f'Movimiento confirmado. Stock: {result["stock"]}')
        st.caption("ENTRADA suma unidades y actualiza el costo promedio ponderado. AJUSTE concilia el total contado. MERMA descuenta unidades dañadas; no registra vencimientos por lote.")
    with annul:
        if "pending_annul" in st.session_state:
            pending=st.session_state.pending_annul
            st.warning("Anulación pendiente de confirmación.")
            if st.button("Reintentar anulación"):
                repo.annul(**pending); del st.session_state["pending_annul"]; finish("Venta anulada.")
        else:
            headers=repo.recent_table("bodega_ventas",30)
            valid=headers.loc[headers.estado=="COMPLETADA"] if not headers.empty else headers
            if valid.empty: st.info("No hay ventas para anular.")
            else:
                last=valid.tail(30)
                st.dataframe(present_activity(last),hide_index=True,width="stretch")
                with st.form("annul_form"):
                    vid=st.selectbox("Venta a anular",last.id.tolist())
                    reason=st.text_input("Motivo de anulación",max_chars=200)
                    confirm=st.checkbox("Revisé la venta seleccionada y confirmo su anulación")
                    submit=st.form_submit_button("Anular venta")
                if submit:
                    if not confirm or len(reason.strip())<3: st.error("Completa el motivo y la confirmación.")
                    else:
                        pending={"op":str(uuid4()),"vid":int(vid),"reason":reason.strip()}
                        st.session_state["pending_annul"]=pending
                        repo.annul(**pending); del st.session_state["pending_annul"]
                        notify(repo,"venta_anulada"); finish("Venta anulada. El tablero excluye sus líneas.")
        st.caption("La anulación corrige un ticket completo: restituye el stock de una venta POS y excluye sus importes del BI.")


def replenish_page(repo,products,sales,role):
    hero("Compra con una razón clara", "Sugerencias por ventas recientes, plazo del proveedor y stock mínimo.")
    coverage=st.slider("Días adicionales de cobertura",1,28,7)
    st.caption("Se usan los últimos 28 días hasta hoy en Lima. La sugerencia requiere revisar que el historial esté completo; las ventas realizadas pueden ocultar demanda si hubo faltantes.")
    table=replenish(products,sales,TODAY,coverage)
    if table.empty: st.info("Agrega productos para obtener recomendaciones."); return
    a,b,c=st.columns(3)
    a.metric("Artículos para reponer",int((table.comprar>0).sum()))
    b.metric("Unidades sugeridas",int(table.comprar.sum()))
    c.metric("Costo orientativo",soles(float((table.comprar*table.costo).sum())))
    display=table[["nombre","proveedor","stock","ventas_28d","unidades_dia","comprar","estado","motivo"]]
    st.dataframe(display,hide_index=True,width="stretch")
    export_button(display,"lista_reposicion.csv","Descargar lista de compra")
    st.info("Objetivo = máximo(stock mínimo, redondeo hacia arriba de unidades/día × (plazo + cobertura)). Compra = máximo(0, objetivo − stock). Verifica compras ya pendientes con el proveedor.")
    if role=="administrador":
        if "pending_decision" in st.session_state:
            st.warning("Decisión pendiente de confirmación.")
            if st.button("Reintentar decisión"):
                repo.decision(**st.session_state.pending_decision)
                del st.session_state["pending_decision"]; finish("Decisión guardada.")
        else:
            candidates=table.loc[table.comprar>0]
            if not candidates.empty:
                with st.form("replenish_decision"):
                    labels=dict(zip(candidates.id,candidates.nombre))
                    pid=st.selectbox("Sugerencia a revisar",candidates.id.tolist(),format_func=labels.get)
                    choice=st.radio("Tu decisión",["ACEPTADA","DESCARTADA"],horizontal=True)
                    reason=st.text_input("Motivo de tu decisión",max_chars=200)
                    submit=st.form_submit_button("Guardar decisión")
                if submit:
                    if len(reason.strip())<3:st.error("Escribe el motivo para documentar tu decisión.")
                    else:
                        row=candidates.loc[candidates.id==pid].iloc[0]
                        pending={"op":str(uuid4()),"product_id":int(pid),"units":int(row.comprar),"decision":choice,
                            "reason":reason.strip(),"context":{"corte":str(TODAY),"stock":int(row.stock),
                                "objetivo":int(row.objetivo_stock),"ventas_28d":float(row.ventas_28d),"cobertura":coverage}}
                        st.session_state["pending_decision"]=pending
                        repo.decision(**pending); del st.session_state["pending_decision"]
                        notify(repo,"reposicion_revisada"); finish("Decisión guardada con su motivo.")
        st.caption("Aceptar guarda una intención de compra. El pedido al proveedor y la entrada de mercadería se registran por separado; el stock no aumenta al aceptar.")
    st.subheader("Artículos sin venta en el período")
    st.dataframe(table.loc[table.ventas_28d==0,["nombre","stock","costo"]],hide_index=True,width="stretch")


def forecast_page(repo,products,sales,role,embedded=False):
    from bodega.prediction_page import render
    render(repo,products,sales,role,TODAY,notify,embedded)


def import_page(repo,products,role):
    hero("De tu historial al tablero", "Carga ventas históricas con validación, trazabilidad del lote y control de duplicados.")
    if role!="administrador": st.info("La importación corresponde a administración."); return
    st.warning("El historial importado no resta stock actual. Carga el inventario actual mediante entradas o conteo físico. No vuelvas a importar ventas que ya registraste en esta aplicación.")
    steps=st.columns(4)
    for col,title in zip(steps,["1 · Archivo CSV","2 · Validación","3 · Staging","4 · Ventas y BI"]): col.markdown(f"**{title}**")
    st.download_button("Descargar plantilla CSV",(",".join(COLUMNS)+"\n").encode(),"plantilla_ventas.csv","text/csv")
    st.caption("UTF-8; fecha YYYY-MM-DD; punto decimal; códigos conservados como texto; ticket único global en la bodega. Máximo 2000 líneas y 5 MB.")
    file=st.file_uploader("Archivo de ventas históricas",type=["csv"])
    if file:
        records,errors,sha=validate_csv(file.getvalue(),set(products.codigo) if not products.empty else set())
        if errors:
            st.error(f"{len(errors)} filas con errores. Corrige el archivo; este lote no se cargará parcialmente.")
            st.dataframe(pd.DataFrame(errors),hide_index=True,width="stretch")
        else:
            st.success(f"{len(records)} líneas válidas · {len(set(r['ticket'] for r in records))} tickets")
            st.dataframe(pd.DataFrame(records).head(20),hide_index=True,width="stretch")
            if st.button("Guardar lote validado en staging",type="primary"):
                batch_id=st.session_state.setdefault("upload_ids",{}).setdefault(sha,str(uuid4()))
                result=repo.create_batch(batch_id,file.name,sha,records)
                st.session_state["last_batch"]=result["lote_id"]
                notify(repo,"lote_validado"); finish("Lote guardado. Procesa el lote pendiente para actualizar el tablero.")
    batches=repo.table("bodega_lotes")
    if not batches.empty:
        st.subheader("Lotes y estado")
        st.dataframe(present_activity(batches),hide_index=True,width="stretch")
        pending=batches.loc[batches.estado=="VALIDADO"]
        if not pending.empty:
            labels=dict(zip(pending.id,pending.nombre))
            batch_id=st.selectbox("Lote pendiente",pending.id.tolist(),format_func=labels.get)
            if st.button("Procesar lote → actualizar BI",type="primary"):
                result=repo.process_batch(batch_id)
                notify(repo,"lote_procesado"); finish(f'{result["filas"]} líneas procesadas. Ya puedes consultar el tablero.')


def activity_page(repo,role):
    hero("Actividad y trazabilidad", "Consulta movimientos, importaciones y pronósticos guardados.")
    if role=="administrador":
        team_editor()
        from bodega.charge_wait import admin,diagnostics
        diagnostics(repo)
        admin(repo)
    names={"Movimientos":"bodega_movimientos","Ventas y pagos":"bodega_ventas","Lotes":"bodega_lotes","Pronósticos":"bodega_predicciones","Decisiones de reposición":"bodega_reposiciones"}
    if role=="administrador": names["Eventos de uso"]="bodega_eventos"
    selected=st.selectbox("Datos",list(names))
    data=repo.recent_table(names[selected])
    st.caption("Se muestran hasta 250 registros recientes. Para ventas con filtros y reimpresión utiliza Historial de ventas.")
    if data.empty: st.info("Aún no hay registros.")
    else:
        data=present_activity(data)
        st.dataframe(data,hide_index=True,width="stretch")
        export_button(data,selected.lower().replace(" ","_")+".csv")
        st.caption("Los nombres y roles reflejan el directorio actual. Si aparece «Usuario sin nombre», asígnalo en Equipo y nombres. La auditoría conserva el identificador original.")
    with st.expander("Cómo se calculan los indicadores"):
        st.write("Ventas netas: suma de importes de líneas de ventas completadas. Ticket promedio: ventas / tickets únicos. Velocidad: unidades realizadas / días calendario. Stock: entradas y ajustes menos ventas y mermas, más anulaciones POS. Fiados distingue ventas a crédito, abonos y deuda pendiente. Las devoluciones parciales y la emisión tributaria requieren un desarrollo adicional.")


def main():
    app_mode=mode()
    if app_mode=="demo":
        
        if "demo_repo" not in st.session_state:
            st.session_state["demo_repo"]=DemoRepository()
        repo=st.session_state["demo_repo"]
        role="administrador"
    else:
        if "identity" not in st.session_state:
            hero("Bienvenido a Bodega Marga", "Accede con tu cuenta asignada para registrar ventas y revisar tu inventario.")
            with st.form("login"):
                email=st.text_input("Correo",max_chars=180)
                password=st.text_input("Contraseña",type="password",key="login_password")
                submit=st.form_submit_button("Ingresar",type="primary")
                verification=st.form_submit_button("Enviar correo de verificación")
            if submit:
                login(email.strip(),password)
                # La contraseña queda exclusivamente en el formulario; no se guarda en identidad.
                st.rerun()
            if verification:
                send_verification(email.strip(),password)
                st.success("Revisa tu correo y confirma el enlace. Después inicia sesión.")
            st.caption("El propietario habilita las cuentas en Firebase Authentication y asigna los roles.")
            return
        try: identity=require_identity()
        except AccessError as exc:
            logout(); st.error(str(exc)); return
        role=identity["role"]
        repo=st.session_state.get("cloud_repo")
        from bodega.config import setting
        if repo is None or repo.url!=str(setting("SUPABASE_URL")).strip().rstrip("/") or repo.key!=str(setting("SUPABASE_SERVICE_ROLE_KEY")).strip():
            if repo is not None: repo.http.close()
            repo=CloudRepository()
            st.session_state["cloud_repo"]=repo
    products=enrich_products(repo.table("bodega_productos"),repo.table("bodega_categorias"),repo.table("bodega_proveedores"))
    page=storefront.topbar(products,role,app_mode,logout,repo=repo)
    # Caja e inventario no necesitan descargar todo el historial en cada clic.
    sales=prepare_sales(pd.DataFrame())
    if page in {"Resumen BI","Pronóstico"}:
        sales=prepare_sales(repo.table("bodega_v_ventas"))
    elif page in {"Inicio","Reposición"} or (page=="Registrar venta" and st.session_state.get("catalog_sort")=="Más vendidos"):
        days=7 if page=="Inicio" else 28
        sales=prepare_sales(repo.table("bodega_v_ventas",since=TODAY-timedelta(days=days-1),until=TODAY))
    screen=f"{page}/{st.session_state.get('shop_view','catalogo')}" if page=="Registrar venta" else page
    if st.session_state.get("measured_screen")!=screen:
        event=("caja_abierta" if st.session_state.get("shop_view")=="carrito" else "catalogo_abierto") if page=="Registrar venta" else "pagina_visitada"
        record(repo,event,page=screen)
        st.session_state["measured_screen"]=screen
    if "flash" in st.session_state: st.success(st.session_state.pop("flash"))
    if page=="Inicio":home_page(products,sales,role)
    elif page=="Resumen BI": overview(repo,products,sales,role)
    elif page=="Registrar venta": sale_page(repo,products,role,sales)
    elif page=="Historial de ventas":
        from bodega.sales_history import render
        render(repo,role,TODAY)
    elif page=="Fiados":
        from bodega.credit import render
        render(repo,role,TODAY)
    elif page=="Inventario": inventory_page(repo,products,role)
    elif page=="Reposición": replenish_page(repo,products,sales,role)
    elif page=="Pronóstico": forecast_page(repo,products,sales,role)
    elif page=="Importar historial": import_page(repo,products,role)
    else: activity_page(repo,role)
    footer()


try:
    with identity_scope():
        main()
except (DataError,AccessError,ValueError) as exc:
    if isinstance(exc,DataError) and exc.confirmed_rejected:
        if "pending_sale" in st.session_state:
            st.session_state["reset_payment_confirmation"]=True
        for key in ["pending_sale","pending_movement","pending_annul","pending_decision"]:
            st.session_state.pop(key,None)
    st.error(str(exc))
    if st.button("Volver a cargar"):
        st.rerun()
