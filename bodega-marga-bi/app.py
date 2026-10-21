from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4
from pathlib import Path
import html
import pandas as pd
import plotly.express as px
import streamlit as st

from bodega.config import mode
from bodega.auth import AccessError, login, require_identity, logout, send_verification
from bodega.repository import CloudRepository, DataError
from bodega.demo import DemoRepository
from bodega.imports import validate_csv, COLUMNS
from bodega.analytics import prepare_sales, enrich_products, kpis, replenish, daily_series, forecast, csv_export

st.set_page_config(page_title="Bodega Marga · BI", page_icon="🛒", layout="wide")
st.markdown('''<style>
.block-container{max-width:1450px;padding-top:2rem;padding-bottom:2rem}
section[data-testid="stSidebar"]{background:#edf3ee;border-right:1px solid #d9e5dc}
.brand{font-weight:800;font-size:1.4rem;letter-spacing:-.04em;color:#173b32}
.kicker{font-size:.72rem;font-weight:750;letter-spacing:.15em;color:#127c64;margin-bottom:10px}
.hero{border-radius:20px;background:#173b32;color:#fff;padding:30px 34px;margin:0 0 22px}
.hero h1{font-size:2rem;letter-spacing:-.045em;color:#fff;margin:0 0 10px;padding:0}
.hero p{color:#d0e6d7;max-width:800px;margin:0;font-size:1rem}
.hero .kicker{color:#afdec6}
div[data-testid="stMetric"]{background:white;border:1px solid #dfe9e1;padding:16px;border-radius:14px}
div[data-testid="stMetricValue"]{font-weight:750;letter-spacing:-.04em}
div[data-testid="stDataFrame"]{border:1px solid #dfe9e1;border-radius:12px}
.stButton>button{border-radius:9px}
</style>''', unsafe_allow_html=True)

ROOT = Path(__file__).resolve().parent
TODAY = datetime.now(ZoneInfo("America/Lima")).date()
PAGES = ["Inicio", "Registrar venta", "Inventario", "Resumen BI", "Reposición", "Pronóstico", "Importar historial", "Actividad y datos"]


def soles(value):
    return f"S/ {value:,.2f}"


def hero(title, text):
    st.markdown(f'<div class="hero"><div class="kicker">BODEGA MARGA · LOS OLIVOS</div><h1>{html.escape(title)}</h1><p>{html.escape(text)}</p></div>',unsafe_allow_html=True)


def chart(fig):
    fig.update_layout(font={"family":"Arial","color":"#173b32"},paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",margin={"t":30,"b":20,"l":20,"r":15},height=330)
    st.plotly_chart(fig,width="stretch")


def notify(repo,event,detail=""):
    # Telemetría de uso sin emails, nombres de clientes ni credenciales.
    try:
        repo.event(event,detail)
    except (DataError,AccessError):
        st.caption("La operación se confirmó; no se pudo registrar su evento de uso.")


def finish(message):
    st.session_state["flash"]=message
    st.rerun()


def export_button(df,filename,label="Descargar CSV"):
    st.download_button(label,csv_export(df),filename,"text/csv")


def go_to(page):
    st.session_state["page"]=page


def home_page(products,sales,role):
    hero("Tu bodega, de un vistazo", "Revisa el día y encuentra rápidamente tu próxima tarea.")
    daily=sales.loc[sales.fecha==pd.Timestamp(TODAY)]
    values=kpis(daily)
    active=products.loc[products.activo] if not products.empty else products
    low=active.loc[active.stock<=active.stock_minimo] if not active.empty else active
    a,b,c=st.columns(3)
    a.metric("Ventas de hoy",soles(values["ventas"])); b.metric("Artículos en alerta",len(low)); c.metric("Productos activos",len(active))
    st.caption(f"Día de operación en Lima: {TODAY.strftime('%d/%m/%Y')}")
    a,b=st.columns([1.4,1])
    with a:
        st.subheader("Tus tareas frecuentes")
        if role in {"administrador","cajero"}:
            st.button("+ Registrar venta",type="primary",on_click=go_to,args=("Registrar venta",))
        st.button("Ver reposición sugerida",on_click=go_to,args=("Reposición",))
        st.subheader("Últimas ventas")
        if sales.empty:st.info("Aún no hay ventas.")
        else:
            recent=sales.groupby(["venta_id","fecha","medio_pago","origen"],as_index=False).agg(total=("ingreso","sum"),unidades=("cantidad","sum"))
            st.dataframe(recent.sort_values(["fecha","venta_id"],ascending=False).head(8),hide_index=True,width="stretch")
    with b:
        st.subheader("Pendientes de revisar")
        if low.empty:st.success("No hay artículos por debajo de su mínimo.")
        else:st.dataframe(low[["nombre","stock","stock_minimo"]],hide_index=True,width="stretch")
        st.button("Ir a inventario",on_click=go_to,args=("Inventario",))
    if not sales.empty:
        start=pd.Timestamp(TODAY)-pd.Timedelta(days=6)
        chartdata=sales.loc[sales.fecha>=start].groupby("fecha").ingreso.sum().reindex(pd.date_range(start,TODAY),fill_value=0).rename_axis("fecha").reset_index(name="ingreso")
        st.subheader("Ventas de los últimos 7 días")
        chart(px.bar(chartdata,x="fecha",y="ingreso",color_discrete_sequence=["#127c64"],labels={"ingreso":"Ventas S/","fecha":"Día"}))


def overview(products,sales):
    hero("Tus datos, tus próximas decisiones", "Ventas, existencias y reposición en una sola vista. Elige el período que quieres revisar.")
    if sales.empty:
        st.info("Aún no hay ventas. Registra una venta o importa tu historial para empezar.")
    cutoff = sales.fecha.max().date() if not sales.empty else TODAY
    a,b,c=st.columns([2,2,1])
    dates=a.date_input("Período",value=(cutoff-timedelta(days=27),cutoff),key="bi_dates")
    categories=sorted(products.categoria.unique()) if not products.empty else []
    selected=b.multiselect("Categorías",categories,default=categories)
    source=c.selectbox("Origen",["Todos","POS","HISTORICO"])
    filtered=sales.copy()
    if len(dates)!=2:
        st.info("Selecciona una fecha inicial y final."); return
    filtered=filtered.loc[(filtered.fecha>=pd.Timestamp(dates[0])) & (filtered.fecha<=pd.Timestamp(dates[1])) & filtered.categoria.isin(selected)]
    if source!="Todos": filtered=filtered.loc[filtered.origen==source]
    values=kpis(filtered)
    m=st.columns(4)
    m[0].metric("Ventas netas",soles(values["ventas"]))
    m[1].metric("Tickets",values["tickets"])
    m[2].metric("Ticket promedio",soles(values["ticket_promedio"]))
    m[3].metric("Margen bruto estimado",soles(values["margen"]))
    st.caption("Ventas netas = precio × unidades − descuento. Margen bruto = ventas − costo registrado; no equivale a utilidad neta. Ticket promedio por ticket único, dentro del filtro.")
    left,right=st.columns([1.5,1])
    with left:
        st.subheader("Cómo van tus ventas")
        if not filtered.empty:
            daily=filtered.groupby("fecha",as_index=False).ingreso.sum()
            chart(px.area(daily,x="fecha",y="ingreso",color_discrete_sequence=["#127c64"],labels={"ingreso":"Ventas S/","fecha":"Día"}))
        else: st.info("Sin ventas para estos filtros.")
    with right:
        st.subheader("Productos que más aportan")
        if not filtered.empty:
            top=filtered.groupby("nombre",as_index=False).ingreso.sum().nlargest(7,"ingreso").sort_values("ingreso")
            chart(px.bar(top,y="nombre",x="ingreso",orientation="h",color_discrete_sequence=["#e1a14a"],labels={"ingreso":"Ventas S/","nombre":""}))
    l,r=st.columns(2)
    with l:
        st.subheader("Ventas por categoría")
        if not filtered.empty:
            grouped=filtered.groupby("categoria",as_index=False).ingreso.sum()
            chart(px.pie(grouped,names="categoria",values="ingreso",hole=.55,color_discrete_sequence=["#127c64","#e1a14a","#73aa97","#9fbdc2","#527466"]))
    with r:
        st.subheader("Qué requiere atención ahora")
        if not products.empty:
            active=products.loc[products.activo]
            low=active.loc[active.stock<=active.stock_minimo]
            st.metric("Artículos con stock bajo o agotado",len(low))
            st.dataframe(low[["codigo","nombre","stock","stock_minimo"]],hide_index=True,width="stretch")
        st.caption("Stock actual: no cambia al seleccionar otro período en el tablero.")
    if not filtered.empty:
        st.subheader("Detalle del período")
        table=filtered[["fecha","venta_id","nombre","categoria","cantidad","ingreso","margen_bruto","medio_pago","origen"]]
        st.dataframe(table,hide_index=True,width="stretch")
        export_button(table,"ventas_bodega_marga.csv")


def sale_page(repo,products,role):
    hero("Registra una venta", "Busca por nombre o código, agrega artículos y confirma la venta.")
    if role not in {"administrador","cajero"}:
        st.info("Tu rol permite consultar el análisis. El registro de ventas corresponde a caja o administración."); return
    if "pending_sale" in st.session_state:
        pending=st.session_state.pending_sale
        st.warning("La venta está pendiente de confirmación. Reintenta con los mismos datos para evitar duplicarla.")
        st.write(pd.DataFrame(pending["items"]))
        if st.button("Reintentar venta pendiente",type="primary"):
            result=repo.sale(pending["op"],pending["items"],pending["payment"])
            del st.session_state["pending_sale"]; st.session_state["cart"]=[]
            finish(f'Venta {result["venta_id"]} confirmada · {soles(float(result["total"]))}')
        return
    active=products.loc[products.activo & (products.stock>0)] if not products.empty else products
    if active.empty:
        st.info("No hay productos con existencias. Administración debe registrar el catálogo y las entradas."); return
    cart=st.session_state.setdefault("cart",[])
    options={int(p.id):f"{p.nombre} · {p.codigo} · {soles(p.precio)} · {p.stock:g} u." for p in active.itertuples()}
    with st.form("add_to_cart",clear_on_submit=True):
        a,b,c=st.columns([3,1,1])
        pid=a.selectbox("Producto · escribe el código o nombre",list(options),format_func=options.get)
        qty=b.number_input("Cantidad",min_value=1,max_value=100000,value=1,step=1)
        disc=c.number_input("Descuento de esta línea S/",min_value=0.0,value=0.0,step=.1)
        add=st.form_submit_button("Agregar al carrito")
    if add:
        p=active.loc[active.id==pid].iloc[0]
        old=next((x for x in cart if x["producto_id"]==pid),None)
        totalqty=qty+(old["cantidad"] if old else 0)
        totaldisc=round(disc+(old["descuento"] if old else 0),2)
        if totalqty>p.stock or totaldisc>totalqty*p.precio:
            st.error("Revisa la cantidad, el descuento y el stock disponible.")
        elif old:
            old.update(cantidad=totalqty,descuento=totaldisc)
        else: cart.append({"producto_id":pid,"cantidad":qty,"descuento":round(disc,2)})
    if not cart:
        st.caption("Tu carrito está vacío."); return
    rows=[]
    for x in cart:
        p=products.loc[products.id==x["producto_id"]].iloc[0]
        rows.append({"Producto":p.nombre,"Cantidad":x["cantidad"],"Precio S/":p.precio,
            "Descuento S/":x["descuento"],"Total S/":round(x["cantidad"]*p.precio-x["descuento"],2)})
    st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch")
    a,b=st.columns(2)
    payment=a.selectbox("Medio de pago",["Efectivo","Yape","Plin","Tarjeta","Transferencia"])
    b.metric("Total a cobrar",soles(sum(r["Total S/"] for r in rows)))
    if st.button("Confirmar venta",type="primary"):
        pending={"op":str(uuid4()),"items":[dict(x) for x in cart],"payment":payment}
        st.session_state["pending_sale"]=pending
        result=repo.sale(pending["op"],pending["items"],pending["payment"])
        del st.session_state["pending_sale"]; st.session_state["cart"]=[]
        notify(repo,"venta_confirmada")
        finish(f'Venta {result["venta_id"]} confirmada · {soles(float(result["total"]))}')
    if st.button("Vaciar carrito"):
        st.session_state["cart"]=[]; st.rerun()
    st.caption("El precio y el stock se verifican al confirmar. Registro interno: no emite comprobantes electrónicos.")


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
        with st.form("catalog_form"):
            a,b=st.columns(2)
            code=a.text_input("Código / código de barras",value=p.get("codigo",""),max_chars=60)
            name=b.text_input("Nombre",value=p.get("nombre",""),max_chars=120)
            category=a.text_input("Categoría",value=p.get("categoria","Abarrotes"),max_chars=80)
            supplier=b.text_input("Proveedor",value=p.get("proveedor","Proveedor local"),max_chars=100)
            price=a.number_input("Precio de venta S/",min_value=0.0,value=float(p.get("precio",0)),step=.1)
            cost=b.number_input("Costo de referencia S/",min_value=0.0,value=float(p.get("costo",0)),step=.1)
            minimum=a.number_input("Stock mínimo",min_value=0,value=int(p.get("stock_minimo",5)),step=1)
            lead=b.number_input("Plazo del proveedor (días)",min_value=0,max_value=90,value=int(p.get("plazo_dias",2)),step=1)
            enabled=st.checkbox("Producto activo",value=bool(p.get("activo",True)))
            submit=st.form_submit_button("Guardar producto",type="primary")
        if submit:
            if not all(x.strip() for x in [code,name,category,supplier]): st.error("Completa los campos de texto.")
            else:
                repo.save_product({"id":int(pid) if pid is not None else None,"codigo":code.strip(),"nombre":name.strip(),
                    "categoria":category.strip(),"proveedor":supplier.strip(),"precio":round(price,2),"costo":round(cost,2),
                    "stock_minimo":minimum,"plazo_dias":lead,"activo":enabled})
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
            headers=repo.table("bodega_ventas")
            valid=headers.loc[headers.estado=="COMPLETADA"] if not headers.empty else headers
            if valid.empty: st.info("No hay ventas para anular.")
            else:
                last=valid.tail(30)
                st.dataframe(last,hide_index=True,width="stretch")
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
        st.caption("Anular una venta POS devuelve sus unidades al stock. Anular historia importada solo corrige el análisis. No reemplaza un proceso de devoluciones parciales.")


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


def forecast_page(repo,products,sales,role):
    hero("Pronóstico que se puede comprobar", "Comparamos dos referencias sencillas con Random Forest usando 28 días posteriores al entrenamiento.")
    if products.empty or sales.empty: st.info("Primero carga productos e historial."); return
    ids=products.id.tolist(); labels=dict(zip(products.id,products.nombre))
    pid=st.selectbox("Producto",ids,format_func=labels.get,key="forecast_product")
    a,b,c=st.columns(3)
    start=a.date_input("Inicio del registro completo",value=sales.fecha.min().date(),key="forecast_start")
    end=b.date_input("Fecha de corte",value=sales.fecha.max().date(),max_value=TODAY,key="forecast_end")
    horizon=c.selectbox("Días a pronosticar",[7,14,28])
    complete=st.checkbox("Confirmo que cada día del período tiene registro completo; un día sin líneas significa cero ventas.")
    stockout=st.checkbox("Hubo faltantes o días con ventas sin registrar")
    if stockout: st.warning("El pronóstico no se habilita hasta corregir o delimitar un período completo. Las ventas no equivalen a demanda no atendida.")
    if not complete or stockout:
        st.info("Confirma la cobertura del registro para evaluar el pronóstico."); return
    series=daily_series(sales,int(pid),start,end)
    signature=(int(pid),str(start),str(end),horizon,tuple(series))
    if st.button("Evaluar y pronosticar",type="primary"):
        with st.spinner("Comparando métodos con datos pasados…"):
            result=forecast(series,horizon)
        st.session_state["forecast_result"]=(signature,result)
        notify(repo,"pronostico_evaluado")
    stored=st.session_state.get("forecast_result")
    if not stored or stored[0]!=signature: return
    result=stored[1]
    a,b,c=st.columns(3)
    a.metric("Método elegido",result["metodo"])
    b.metric("WAPE · validación 28 días",f'{100*result["wape"]:.1f}%')
    c.metric("Índice 100 × (1 − WAPE)",f'{result["exactitud"]:.1f}%')
    scores=pd.DataFrame([{"Método":m,"WAPE %":round(100*v,2)} for m,v in result["scores"].items()])
    st.dataframe(scores,hide_index=True,width="stretch")
    st.caption("Menor WAPE es mejor. El índice puede ser negativo y no se fuerza a 80 %. El mismo bloque se usa para seleccionar el método: es validación preliminar, no una prueba final independiente.")
    l,r=st.columns(2)
    with l:
        st.subheader("Comparación sobre semanas reservadas")
        chart(px.line(result["comparison"],x="fecha",y=["observado","baseline","Random Forest"],labels={"value":"Unidades","fecha":"Día"}))
    with r:
        st.subheader("Próximos días")
        chart(px.bar(result["table"],x="fecha",y="unidades",color_discrete_sequence=["#127c64"]))
        st.dataframe(result["table"],hide_index=True,width="stretch")
    export_button(result["table"],"pronostico_unidades.csv")
    if role in {"administrador","analista"} and st.button("Guardar evaluación y pronóstico"):
        records=[{"producto_id":int(pid),"fecha":r.fecha.date().isoformat(),"corte":str(end),
            "unidades":round(float(r.unidades),3),"metodo":result["metodo"],
            "wape_validacion":result["wape"],"wape_baseline":result["wape_baseline"]} for r in result["table"].itertuples()]
        repo.save_forecast(records); st.success("Pronóstico guardado.")


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
        st.dataframe(batches,hide_index=True,width="stretch")
        pending=batches.loc[batches.estado=="VALIDADO"]
        if not pending.empty:
            labels=dict(zip(pending.id,pending.nombre))
            batch_id=st.selectbox("Lote pendiente",pending.id.tolist(),format_func=labels.get)
            if st.button("Procesar lote → actualizar BI",type="primary"):
                result=repo.process_batch(batch_id)
                notify(repo,"lote_procesado"); finish(f'{result["filas"]} líneas procesadas. Ya puedes consultar el tablero.')


def activity_page(repo,role):
    hero("Actividad y trazabilidad", "Consulta movimientos, importaciones y pronósticos guardados.")
    names={"Movimientos":"bodega_movimientos","Lotes":"bodega_lotes","Pronósticos":"bodega_predicciones","Decisiones de reposición":"bodega_reposiciones"}
    if role=="administrador": names["Eventos de uso"]="bodega_eventos"
    selected=st.selectbox("Datos",list(names))
    data=repo.table(names[selected])
    if data.empty: st.info("Aún no hay registros.")
    else:
        st.dataframe(data,hide_index=True,width="stretch")
        export_button(data,selected.lower().replace(" ","_")+".csv")
    with st.expander("Cómo se calculan los indicadores"):
        st.write("Ventas netas: suma de importes de líneas de ventas completadas. Ticket promedio: ventas / tickets únicos. Velocidad: unidades realizadas / días calendario. Stock: entradas y ajustes menos ventas y mermas, más anulaciones POS. Las devoluciones parciales, cuentas por cobrar e impuestos están fuera del MVP.")


def main():
    app_mode=mode()
    if app_mode=="demo":
        st.warning("DEMOSTRACIÓN · datos sintéticos. Los cambios viven solo en esta sesión y se pierden al cerrarla.")
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
        repo=CloudRepository()
    with st.sidebar:
        st.markdown('<div class="brand">🛒 Bodega Marga</div><div class="kicker">TIENDA INTELIGENTE · BI</div>',unsafe_allow_html=True)
        st.caption(f"{'Demostración' if app_mode=='demo' else 'Nube'} · {role}")
        available=PAGES if role=="administrador" else [p for p in PAGES if p!="Importar historial" and (role=="cajero" or p!="Registrar venta")]
        page=st.radio("Tu espacio",available,key="page")
        st.divider()
        if app_mode=="demo":
            if st.button("Reiniciar demostración"):
                logout(); st.rerun()
        elif st.button("Cerrar sesión"):
            logout(); st.rerun()
        st.caption("Los Olivos, Lima · soles (PEN)")
    if "flash" in st.session_state: st.success(st.session_state.pop("flash"))
    products=enrich_products(repo.table("bodega_productos"),repo.table("bodega_categorias"),repo.table("bodega_proveedores"))
    sales=prepare_sales(repo.table("bodega_v_ventas"))
    if page=="Inicio":home_page(products,sales,role)
    elif page=="Resumen BI": overview(products,sales)
    elif page=="Registrar venta": sale_page(repo,products,role)
    elif page=="Inventario": inventory_page(repo,products,role)
    elif page=="Reposición": replenish_page(repo,products,sales,role)
    elif page=="Pronóstico": forecast_page(repo,products,sales,role)
    elif page=="Importar historial": import_page(repo,products,role)
    else: activity_page(repo,role)


try:
    main()
except (DataError,AccessError,ValueError) as exc:
    if isinstance(exc,DataError) and exc.confirmed_rejected:
        for key in ["pending_sale","pending_movement","pending_annul","pending_decision"]:
            st.session_state.pop(key,None)
    st.error(str(exc))
    if st.button("Volver a cargar"):
        st.rerun()
