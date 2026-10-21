"""Seis páginas BI con filtros compartidos y visualizaciones de dos columnas."""
from datetime import timedelta
from textwrap import fill
import html
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from bodega import bi
from bodega.analytics import csv_export
from bodega.repository import DataError
from bodega.telemetry import record

PAGES=["Resumen ejecutivo","Ventas y rentabilidad","Diagnóstico e inventario","Cubo OLAP","Predicciones","Datos y uso"]
COLORS=["#2e775f","#dfa77e","#9abfb0","#91a9b5","#bf9f87","#708a79"]
px.defaults.color_discrete_sequence=COLORS


def money(value):return f"S/ {float(value):,.2f}"


def draw(fig,height=310):
    fig.update_layout(font=dict(family="Arial",color="#253d32",size=11),paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",height=height,margin=dict(l=15,r=15,t=25,b=25),
        legend=dict(orientation="h",y=-.22),colorway=COLORS)
    fig.update_xaxes(showgrid=False,automargin=True)
    fig.update_yaxes(gridcolor="#edf0ed",zerolinecolor="#e2e8e2",automargin=True)
    st.plotly_chart(fig,width="stretch",theme=None,config={"displaylogo":False})


def table(data,name,label="Descargar tabla CSV"):
    st.dataframe(data,hide_index=True,width="stretch",height="auto")
    st.download_button(label,csv_export(data),name,"text/csv",key="export_"+name)


def section(title,question):
    st.markdown(f'<div class="bi-section"><h3>{html.escape(title)}</h3><p>{html.escape(question)}</p></div>',unsafe_allow_html=True)


def _step(delta):
    current=st.session_state.get("bi_page",PAGES[0])
    st.session_state["bi_page"]=PAGES[max(0,min(5,PAGES.index(current)+delta))]


def _clear_filters():
    st.session_state.pop("bi_filters",None)
    for key in list(st.session_state):
        if key.startswith("_bif_"):del st.session_state[key]


def filters_panel(data,products,today):
    saved=st.session_state.get("bi_filters",{})
    end=data.fecha.max().date() if not data.empty else today
    state={}
    def value(name,default):
        key="_bif_"+name
        if key not in st.session_state:st.session_state[key]=saved.get(name,default)
        return key
    with st.container(key="bi_filter_panel"):
        st.markdown("**Filtros del análisis**")
        st.caption("Una selección vacía incluye todos los valores.")
        dates=saved.get("dates",(end-timedelta(days=27),end))
        start=st.date_input("Ventas desde",key=value("start",dates[0]),format="DD/MM/YYYY")
        finish=st.date_input("Ventas hasta",key=value("finish",dates[-1]),format="DD/MM/YYYY")
        state["dates"]=(start,finish)
        if start>finish:st.caption("La fecha inicial debe preceder a la final.")
        options=[("years","Años",sorted(data.anio.dropna().unique().tolist())),
            ("months","Meses",list(range(1,13))),
            ("categories","Categorías",sorted(data.categoria.dropna().unique().tolist())),
            ("products","Productos",products.id.tolist() if not products.empty else []),
            ("suppliers","Proveedores",sorted(data.proveedor.dropna().unique().tolist())),
            ("payments","Medios de pago",sorted(data.medio_pago.dropna().unique().tolist())),
            ("origins","Origen",["POS","HISTORICO"])]
        labels=dict(zip(products.id,products.nombre)) if not products.empty else {}
        for name,label,opts in options:
            key=value(name,[])
            st.session_state[key]=[x for x in st.session_state[key] if x in opts]
            formatter=(lambda m:bi.MONTHS[m-1]) if name=="months" else (lambda p:labels.get(p,str(p))) if name=="products" else str
            state[name]=st.multiselect(label,opts,key=key,format_func=formatter,placeholder="Todos")
        st.button("Limpiar filtros",on_click=_clear_filters,width="stretch")
    st.session_state["bi_filters"]=state
    return state


def _four_metrics(data):
    r=bi.aggregate(data).iloc[0]
    a,b,c,d=st.columns(4)
    a.metric("Ventas netas",money(r.ventas));b.metric("Unidades",f"{r.unidades:,.0f}")
    c.metric("Tickets únicos",int(r.tickets));d.metric("Margen bruto",money(r.margen_bruto))
    return r


def summary(repo,products,data,all_data,today):
    metrics=_four_metrics(data)
    st.caption("Ventas y margen corresponden al período filtrado. El margen bruto no equivale a utilidad neta.")
    ranking=bi.product_ranking(data)
    current=bi.inventory(products,all_data,today)
    low=0 if current.empty else int((current.stock<=current.stock_minimo).sum())
    forecasts=repo.table("bodega_predicciones")
    upcoming=forecasts.loc[(pd.to_datetime(forecasts.fecha)>pd.Timestamp(today))&forecasts.producto_id.isin(products.id if not products.empty else [])] if not forecasts.empty else forecasts
    # El resumen informa cobertura, no suma varios cortes superpuestos del mismo producto.
    upcoming_count=upcoming.producto_id.nunique() if not upcoming.empty else 0
    cards=[("Descriptiva","¿Qué se vendió?",money(metrics.ventas),"Ventas netas de los filtros actuales."),
        ("Diagnóstica","¿Qué concentra el resultado?",str(ranking.iloc[0].producto).split(" · ")[-1] if not ranking.empty else "Sin ventas","Mayor aporte en ventas; asociación descriptiva, no causa demostrada."),
        ("Predictiva","¿Qué tenemos proyectado?",f"{upcoming_count} productos","Con pronóstico guardado para días futuros. Evalúa otros en Predicciones."),
        ("Prescriptiva","¿Qué debemos revisar?",f"{low} artículos","Stock actual bajo o agotado; revisar la propuesta de reposición.")]
    for col,(kind,question,value,description) in zip(st.columns(4),cards):
        with col:
            st.markdown('<article class="bi-answer"><span>'+html.escape(kind)+'</span><h4>'+html.escape(question)+
                '</h4><strong>'+html.escape(value)+'</strong><p>'+html.escape(description)+'</p></article>',unsafe_allow_html=True)
    left,right=st.columns([1.4,1])
    with left:
        section("Evolución de ventas","¿Cómo cambia el ingreso registrado dentro del período?")
        if not data.empty:draw(px.area(bi.aggregate(data,["periodo_dia"]),x="periodo_dia",y="ventas",labels={"periodo_dia":"Fecha","ventas":"Ventas S/"}))
        else:st.info("No hay ventas con estos filtros.")
    with right:
        section("Participación por categoría","¿Qué grupos de productos aportan más ventas?")
        if not data.empty:draw(px.pie(bi.aggregate(data,["categoria"]),names="categoria",values="ventas",hole=.65,color_discrete_sequence=COLORS))
    section("Prioridades del inventario","Existencias actuales; el período de ventas no reconstruye stock histórico.")
    if not current.empty:
        table(current[["nombre","stock","stock_minimo","comprar","prioridad"]].head(8),"bi_prioridades.csv")


def sales_page(data):
    metrics=_four_metrics(data)
    if data.empty:st.info("No hay ventas con estos filtros.");return
    granularity=st.selectbox("Agrupar tendencia por",["Día","Mes","Trimestre","Año"],key="bi_sales_grain")
    left,right=st.columns(2)
    with left:
        section("Ventas y margen en el tiempo","Elige el nivel temporal para comparar resultados.")
        draw(px.line(bi.aggregate(data,[bi.DIMENSIONS[granularity]]),x=bi.DIMENSIONS[granularity],y=["ventas","margen_bruto"],markers=True,
            labels={"value":"S/","variable":"Medida",bi.DIMENSIONS[granularity]:granularity}))
    with right:
        section("Productos por aporte","Ventas netas y margen de los diez artículos de mayor ingreso.")
        top=bi.product_ranking(data).head(10).sort_values("ventas")
        fig=px.bar(top,y="producto",x=["ventas","margen_bruto"],orientation="h",barmode="group",labels={"value":"S/","producto":""})
        fig.update_yaxes(tickmode="array",tickvals=top.producto,ticktext=top.producto.str.split(" · ",n=1).str[-1])
        draw(fig)
    a,b=st.columns(2)
    with a:
        section("Medios de pago","Distribución del importe registrado; no procesa cobros.")
        draw(px.pie(bi.aggregate(data,["medio_pago"]),names="medio_pago",values="ventas",hole=.6,color_discrete_sequence=COLORS))
    with b:
        section("Días de mayor actividad","Unidades vendidas por día de la semana.")
        grouped=bi.aggregate(data,["dia_semana"])
        draw(px.bar(grouped,x="dia_semana",y="unidades",category_orders={"dia_semana":bi.WEEKDAYS},labels={"dia_semana":"Día","unidades":"Unidades"}))
    a,b,c=st.columns(3)
    a.metric("Ticket promedio",money(metrics.ticket_promedio) if pd.notna(metrics.ticket_promedio) else "—")
    b.metric("Margen bruto / ventas",f"{metrics.margen_porcentaje:.1f}%" if pd.notna(metrics.margen_porcentaje) else "—")
    c.metric("Descuentos",money(metrics.descuentos))
    detail=st.radio("Tabla comercial",["Productos","Categorías","Proveedores","Tickets","Líneas de venta"],horizontal=True)
    dims={"Productos":["producto","categoria"],"Categorías":["categoria"],"Proveedores":["proveedor"],"Tickets":["venta_id","periodo_dia","medio_pago"]}
    result=bi.aggregate(data,dims[detail]) if detail in dims else data[["fecha","venta_id","codigo","nombre","categoria","cantidad","precio_unitario","descuento","ingreso","margen_bruto","medio_pago","origen"]]
    table(result,"bi_comercial.csv")
    st.caption("Los tickets de categorías y productos pueden compartir una venta: no sumes sus conteos. El total se calcula con tickets distintos; el margen % se calcula como margen total / ventas totales.")


def diagnosis(products,data,all_data,today):
    section("Concentración y rentabilidad","¿Qué artículos concentran ingresos y cuáles conviene revisar?")
    ranking=bi.product_ranking(data)
    left,right=st.columns(2)
    with left:
        st.markdown("**Pareto de ventas · clasificación ABC**")
        if not ranking.empty:
            top=ranking.head(8)
            fig=make_subplots(specs=[[{"secondary_y":True}]])
            positions=list(range(len(top)))
            fig.add_trace(go.Bar(x=positions,y=top.ventas,name="Ventas S/",marker_color=COLORS[0],customdata=top.producto,hovertemplate="%{customdata}<br>S/ %{y:.2f}<extra></extra>"),secondary_y=False)
            fig.add_trace(go.Scatter(x=positions,y=top.acumulado_pct,name="Acumulado %",mode="lines+markers",line_color=COLORS[1]),secondary_y=True)
            fig.update_xaxes(tickmode="array",tickvals=positions,ticktext=[fill(str(x).split(" · ")[-1],12).replace("\n","<br>") for x in top.producto],tickangle=0,tickfont=dict(size=9))
            fig.update_yaxes(range=[0,105],title_text="Acumulado %",secondary_y=True)
            draw(fig,height=390)
            st.caption("Se muestran hasta ocho artículos; el acumulado usa las ventas de todos los productos filtrados.")
        else:st.info("No hay ventas para clasificar.")
    with right:
        st.markdown("**Volumen frente a margen**")
        if not ranking.empty:
            draw(px.scatter(ranking,x="unidades",y="margen_porcentaje",size="ventas",color="categoria",hover_name="producto",
                color_discrete_sequence=COLORS,labels={"unidades":"Unidades vendidas","margen_porcentaje":"Margen bruto %"}))
        st.caption("Una relación observada no demuestra una causa. Se comparan artículos y su margen registrado.")
    if not ranking.empty:
        with st.expander("Ver clasificación ABC y rentabilidad"):
            table(ranking,"bi_abc_rentabilidad.csv")
        st.caption("ABC por ventas: A hasta cruzar 80 % acumulado, B hasta cruzar 95 %, C el resto. Se conserva el artículo que cruza el umbral en el grupo anterior.")
    current=bi.inventory(products,all_data,today)
    section("Existencias y cobertura","Stock de hoy y velocidad de venta de los últimos 28 días calendario.")
    if current.empty:st.info("No hay productos para los filtros elegidos.");return
    a,b,c=st.columns(3)
    a.metric("Valor a costo",money(current.valor_costo.sum()))
    b.metric("Agotados",int(current.stock.eq(0).sum()))
    c.metric("Sin ventas en 28 días",int(current.ventas_28d.eq(0).sum()))
    a,b=st.columns(2)
    with a:
        section("Estado por categoría","¿Dónde se concentra el inventario pendiente de revisión?")
        counts=current.groupby(["categoria","prioridad"],as_index=False).size()
        draw(px.bar(counts,x="categoria",y="size",color="prioridad",barmode="stack",color_discrete_sequence=COLORS,labels={"size":"Artículos"}))
    with b:
        section("Stock frente al mínimo","Los diez artículos con mayor compra sugerida.")
        draw(px.bar(current.head(10),y="nombre",x=["stock","stock_minimo"],orientation="h",barmode="group",labels={"value":"Unidades","nombre":""}))
    state=st.multiselect("Estado actual del inventario",["Agotado","Prioritario","Disponible"],key="bi_stock_states")
    view=current.loc[current.prioridad.isin(state)] if state else current
    table(view[["codigo","nombre","categoria","proveedor","stock","stock_minimo","ventas_28d","unidades_dia","cobertura_dias","comprar","valor_costo","prioridad"]],"bi_inventario_cobertura.csv")
    st.caption("Cobertura vacía = no hubo ventas en la ventana; no equivale a cobertura garantizada. La fecha y el medio de pago del filtro comercial no alteran el stock actual. La sugerencia no descuenta pedidos pendientes ni aumenta existencias.")


def olap(data):
    if data.empty:st.info("No hay hechos de venta para construir el cubo con estos filtros.");return
    st.caption("Grano: una línea de producto por ticket completado. Dimensiones: tiempo, categoría/producto, proveedor, pago y origen.")
    operation=st.radio("Operación OLAP",["Pivot","Slice","Dice","Drill-down","Roll-up","Cubo y subtotales"],horizontal=True,key="olap_operation")
    scoped=data.copy()
    if operation=="Slice":
        dim=st.selectbox("Dimensión para Slice",list(bi.DIMENSIONS),index=5,key="olap_slice_dim")
        col=bi.DIMENSIONS[dim]
        selected=st.selectbox("Valor de la sección",sorted(scoped[col].dropna().unique().tolist()),key="olap_slice_value")
        scoped=scoped.loc[scoped[col].eq(selected)]
        st.caption("Slice fija un valor de una dimensión y conserva las demás para analizarlas.")
    elif operation=="Dice":
        a,b=st.columns(2)
        d1=a.selectbox("Primera dimensión",list(bi.DIMENSIONS),index=5,key="olap_dice_1")
        d2=b.selectbox("Segunda dimensión",[x for x in bi.DIMENSIONS if x!=d1],index=0,key="olap_dice_2")
        v1=a.multiselect("Valores de la primera dimensión",sorted(scoped[bi.DIMENSIONS[d1]].dropna().unique().tolist()),key="olap_dice_v1")
        v2=b.multiselect("Valores de la segunda dimensión",sorted(scoped[bi.DIMENSIONS[d2]].dropna().unique().tolist()),key="olap_dice_v2")
        if v1:scoped=scoped.loc[scoped[bi.DIMENSIONS[d1]].isin(v1)]
        if v2:scoped=scoped.loc[scoped[bi.DIMENSIONS[d2]].isin(v2)]
        st.caption("Dice combina varias selecciones de dos dimensiones; vacío incluye todos.")
    elif operation=="Drill-down":
        branch=st.radio("Jerarquía",["Categoría → producto","Año → trimestre → mes → día"],horizontal=True)
        if branch.startswith("Categoría"):
            category=st.selectbox("Categoría que quieres detallar",sorted(scoped.categoria.unique()))
            scoped=scoped.loc[scoped.categoria.eq(category)]
            result=bi.aggregate(scoped,["producto"])
        else:
            year=st.selectbox("Año a detallar",sorted(scoped.anio.unique()))
            scoped=scoped.loc[scoped.anio.eq(year)]
            level=st.select_slider("Nivel de detalle",["Trimestre","Mes","Día"],value="Mes")
            if level in {"Mes","Día"}:
                quarter=st.selectbox("Trimestre",["Todos"]+sorted(scoped.trimestre.unique()))
                if quarter!="Todos":scoped=scoped.loc[scoped.trimestre.eq(quarter)]
            if level=="Día":
                month=st.selectbox("Mes a abrir",sorted(scoped.periodo_mes.unique()))
                scoped=scoped.loc[scoped.periodo_mes.eq(month)]
            result=bi.aggregate(scoped,[bi.DIMENSIONS[level]])
        _olap_result(result,"olap_drill.csv");return
    elif operation=="Roll-up":
        grain=st.selectbox("Subir al nivel",["Categoría","Proveedor","Mes","Trimestre","Año"])
        _olap_result(bi.aggregate(scoped,[bi.DIMENSIONS[grain]]),"olap_rollup.csv");return
    elif operation=="Cubo y subtotales":
        dims=st.multiselect("Dimensiones del cubo",list(bi.DIMENSIONS),default=["Mes","Categoría","Medio de pago"],max_selections=3)
        if not dims:st.info("Selecciona al menos una dimensión.");return
        result=bi.cube(scoped,[bi.DIMENSIONS[d] for d in dims])
        table(result,"olap_cubo_subtotales.csv")
        st.caption("TOTAL identifica dimensiones agregadas. Cada máscara es un nivel diferente: no sumes filas de máscaras distintas porque repetirías ventas. Tickets y porcentajes se recalculan para cada subtotal.")
        return
    if scoped.empty:st.info("La sección seleccionada está vacía.");return
    a,b,c=st.columns(3)
    row=a.selectbox("Filas",list(bi.DIMENSIONS),index=5,key="olap_rows")
    column=b.selectbox("Columnas",[x for x in bi.DIMENSIONS if x!=row],index=2,key="olap_columns")
    measure=c.selectbox("Medida",list(bi.MEASURES),key="olap_measure")
    if st.checkbox("Intercambiar filas y columnas",key="olap_swap"):row,column=column,row
    matrix=bi.pivot(scoped,bi.DIMENSIONS[row],bi.DIMENSIONS[column],bi.MEASURES[measure])
    total_label=matrix.attrs.get("total_label","TOTAL")
    heat=matrix.drop(index=total_label,columns=total_label,errors="ignore")
    left,right=st.columns([1.05,1])
    with left:
        section("Matriz OLAP",f"{row} × {column} · {measure}")
        table(matrix.reset_index(),"olap_matriz.csv")
    with right:
        section("Mapa de calor","La intensidad compara las celdas; los totales se presentan en la matriz.")
        if not heat.empty:
            draw(px.imshow(heat.astype(float),aspect="auto",color_continuous_scale=["#f7f4ed","#b5d3c2","#2e775f"],
                labels={"x":column,"y":row,"color":measure},text_auto=".1f" if heat.size<=60 else False))
    st.caption("El total general usa los hechos originales: un ticket presente en varias categorías se cuenta una sola vez. El ticket promedio y el margen % no son sumas ni promedios simples de las celdas.")
    timed=scoped.dropna(subset=["hora"])
    with st.expander("Matriz día de semana × hora · ventas POS con hora conocida"):
        if timed.empty:st.info("No hay horas POS conocidas. El historial importado por fecha no permite reconstruir horas.")
        else:
            m=bi.pivot(timed,"dia_semana","hora","ventas")
            table(m.reset_index(),"olap_dia_hora.csv")


def _olap_result(result,filename):
    if result.empty:st.info("Sin resultados.");return
    dimension=next(x for x in result.columns if x not in bi.aggregate(pd.DataFrame()).columns)
    draw(px.bar(result,x=dimension,y="ventas",labels={"ventas":"Ventas S/"}))
    table(result,filename)


def data_page(repo,products,data,all_data,role,today):
    if role not in {"administrador","analista"}:st.info("El almacén y la calidad de datos corresponden a administración o análisis.");return
    area=st.radio("Revisar",["Almacén de datos","Calidad e importaciones","Uso del sistema"],horizontal=True,key="bi_data_area")
    if area=="Almacén de datos":
        section("Hechos y dimensiones","Consulta las tablas que alimentan el análisis de la bodega.")
        options=["Hechos de venta · filtrados","Dimensión productos","Dimensión categorías","Dimensión proveedores","Dimensión tiempo","Pronósticos guardados","Cubo mensual SQL"]
        selected=st.selectbox("Tabla del almacén",options,key="bi_dw_table")
        if selected==options[0]:view=data[["id_detalle","venta_id","fecha","producto_id","codigo","categoria","proveedor","cantidad","ingreso","margen_bruto","medio_pago","origen"]]
        elif selected==options[1]:view=products[["id","codigo","nombre","categoria_id","categoria","proveedor_id","proveedor","precio","costo","stock","activo"]] if not products.empty else products
        else:
            mapping={options[2]:"bodega_categorias",options[3]:"bodega_proveedores",options[4]:"bodega_tiempo",options[5]:"bodega_predicciones",options[6]:"bodega_v_cubo_ventas"}
            try:view=repo.table(mapping[selected])
            except DataError:
                st.info("Aplica database/04_galeria_y_bi.sql para habilitar el cubo SQL.");return
        from bodega.staff import present_activity
        table(present_activity(view),"bi_almacen.csv")
        st.caption("Los filtros comerciales afectan a los hechos de venta. Las dimensiones y el cubo mensual SQL muestran el almacén completo. Los precios/costos de cada línea son históricos; la categoría y proveedor del catálogo reflejan su clasificación actual.")
        with st.expander("Grano, relaciones y reglas"):
            st.markdown("**Hecho:** producto por ticket completado. **Tiempo:** fecha → año, mes y día de semana. **Producto:** código y datos del artículo, enlazado a categoría y proveedor. **Medidas:** unidades, ventas, costo registrado, descuentos y margen bruto. Pago y origen son dimensiones del ticket. Las anulaciones no aportan a las ventas analíticas.")
    elif area=="Calidad e importaciones":
        section("Trazabilidad de los registros","Distingue ventas POS, historial importado y lotes pendientes.")
        batches=repo.table("bodega_lotes")
        a,b,c=st.columns(3)
        a.metric("Líneas completadas",len(all_data));b.metric("Lotes guardados",len(batches))
        c.metric("Lotes pendientes",0 if batches.empty else int(batches.estado.eq("VALIDADO").sum()))
        checks=pd.DataFrame([
            {"Control":"Líneas duplicadas ticket/producto","Casos":int(all_data.duplicated(["venta_id","producto_id"]).sum())},
            {"Control":"Productos del hecho sin catálogo","Casos":int((~all_data.producto_id.isin(products.id if not products.empty else [])).sum())},
            {"Control":"Fechas no interpretables","Casos":int(all_data.fecha.isna().sum())},
            {"Control":"Líneas con margen negativo","Casos":int(all_data.margen_bruto.lt(0).sum())},
            {"Control":"Líneas sin hora POS conocida","Casos":int(all_data.hora.isna().sum())}])
        a,b=st.columns(2)
        with a:table(checks,"bi_calidad.csv")
        with b:
            if not all_data.empty:draw(px.bar(bi.aggregate(all_data,["origen"]),x="origen",y="lineas",labels={"lineas":"Líneas de venta"}))
        st.caption("Sin hora o margen negativo son condiciones a revisar, no necesariamente errores. Esta página inspecciona el almacén completo, independientemente de los filtros comerciales.")
        if not batches.empty:
            from bodega.staff import present_activity
            table(present_activity(batches),"bi_lotes.csv")
        st.caption("CSV → validación → staging → ventas completadas → BI. Los lotes históricos no descuentan existencias actuales.")
    else:
        if role!="administrador":st.info("Los eventos de uso están disponibles para administración.");return
        events=repo.table("bodega_eventos")
        section("Actividad interna medida","Sesiones de esta aplicación y pasos de venta observados.")
        if events.empty:st.info("Aún no hay eventos registrados.");return
        events=events.copy()
        stamp=pd.to_datetime(events.get("fecha_hora",pd.Series(pd.NaT,index=events.index)),utc=True,errors="coerce",format="mixed")
        events["fecha_evento"]=stamp.dt.tz_convert("America/Lima").dt.date
        dates=st.date_input("Período de actividad",(today-timedelta(days=27),today),key="bi_usage_dates")
        if len(dates)!=2:st.info("Completa el período de actividad.");return
        events=events.loc[pd.to_datetime(events.fecha_evento).between(pd.Timestamp(dates[0]),pd.Timestamp(dates[1]))]
        funnel=bi.ordered_funnel(events)
        sessions=events.sesion_id.nunique() if "sesion_id" in events else 0
        conversion=100*funnel.Sesiones.iloc[-1]/funnel.Sesiones.iloc[0] if funnel.Sesiones.iloc[0]>0 else None
        a,b,c,d=st.columns(4)
        a.metric("Cuentas con eventos",events.usuario_uid.nunique() if "usuario_uid" in events else 0)
        b.metric("Sesiones medidas",sessions);c.metric("Eventos",len(events));d.metric("Conversión observada",f"{conversion:.1f}%" if conversion is not None else "—")
        a,b=st.columns(2)
        with a:draw(go.Figure(go.Funnel(y=funnel.Etapa,x=funnel.Sesiones,marker_color=COLORS)))
        with b:
            if not events.empty:
                counts=events.groupby("evento",as_index=False).size()
                draw(px.bar(counts,x="size",y="evento",orientation="h",labels={"size":"Eventos","evento":""}))
        table(funnel,"bi_embudo_sesiones.csv")
        st.caption("Embudo de sesiones con pasos en orden: catálogo → agregar → caja → confirmar. Una sesión cuenta como máximo una vez por etapa. Conversión = sesiones que completaron el recorrido / sesiones que abrieron catálogo en el período. No acredita abandono definitivo ni usuarios/clientes únicos. Recargar o abrir otra sesión puede generar otro identificador. No se recopilan dispositivo, IP ni datos del cliente.")


def dashboard(repo,products,sales,role,today,prediction_page):
    data=bi.facts(sales)
    st.markdown('<section class="bi-banner"><span class="eyebrow">BODEGA MARGA / INTELIGENCIA DE NEGOCIOS</span><h1>De tus ventas a mejores decisiones.</h1><p>Explora resultados, inventario, escenarios y la trazabilidad de tus datos.</p></section>',unsafe_allow_html=True)
    selected=st.session_state.get("bi_selected",PAGES[0])
    with st.container(key="bi_navigation"):
        page=st.radio("Página BI",PAGES,index=PAGES.index(selected),horizontal=True,key="bi_page",label_visibility="collapsed")
    st.session_state["bi_selected"]=page
    if st.session_state.get("measured_bi_page")!=page:
        record(repo,"pagina_bi_visitada",page,page="BI / "+page)
        st.session_state["measured_bi_page"]=page
    a,b,c=st.columns([6,1.2,1.2])
    a.caption(f"Página {PAGES.index(page)+1} de 6 · {page}")
    b.button("← Anterior",on_click=_step,args=(-1,),disabled=page==PAGES[0],width="stretch")
    c.button("Siguiente →",on_click=_step,args=(1,),disabled=page==PAGES[-1],width="stretch")
    if page=="Predicciones":
        prediction_page(repo,products,sales,role,embedded=True);return
    filters,body=st.columns([1,4.7],gap="large")
    with filters:state=filters_panel(data,products,today)
    with body:
        if len(state["dates"])!=2 or state["dates"][0]>state["dates"][1]:st.info("Selecciona un período válido: inicio anterior o igual al final.");return
        scoped=bi.apply_filters(data,state)
        catalog=bi.filter_products(products,state)
        st.caption(f'{len(scoped):,} líneas de venta · {state["dates"][0]:%d/%m/%Y} al {state["dates"][1]:%d/%m/%Y}')
        if page==PAGES[0]:summary(repo,catalog,scoped,data,today)
        elif page==PAGES[1]:sales_page(scoped)
        elif page==PAGES[2]:diagnosis(catalog,scoped,data,today)
        elif page==PAGES[3]:olap(scoped)
        else:data_page(repo,products,scoped,data,role,today)
