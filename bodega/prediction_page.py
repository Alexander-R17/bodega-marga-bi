"""Proyección de uno o varios productos con evaluación temporal visible."""
import hashlib
import pandas as pd
import plotly.express as px
import streamlit as st
from bodega.forecasting import evaluate_portfolio, stock_scenario, validation_wape, saved_records
from bodega.bi_pages import section, draw, table, money, COLORS
from bodega.ui import page_header


def _plots(future,products,today):
    daily,scenario=stock_scenario(future,products,today)
    a,b,c,d=st.columns(4)
    a.metric("Unidades proyectadas",f"{future.unidades.sum():,.1f}")
    b.metric("Ingreso orientativo",money(future.ingreso_orientativo.sum()))
    c.metric("Productos evaluados",future.producto_id.nunique())
    d.metric("Con faltante proyectado",int(scenario.Primer_faltante.notna().sum()) if not scenario.empty else "—")
    st.caption("Las unidades provienen del método elegido por producto. El ingreso orientativo = unidades × precio actual, sin descuentos futuros. El escenario de existencias parte del stock actual y supone que no entran nuevas compras.")
    a,b=st.columns(2)
    with a:
        section("1 · Unidades previstas","¿Qué volumen de ventas se proyecta después del corte?")
        byday=future.groupby("fecha",as_index=False).unidades.sum()
        draw(px.line(byday,x="fecha",y="unidades",markers=True,labels={"fecha":"Día proyectado","unidades":"Unidades previstas"}))
    with b:
        section("2 · Unidades previstas por producto","¿Qué artículos acumulan mayor volumen en el horizonte?")
        ranking=future.groupby("nombre",as_index=False).unidades.sum().sort_values("unidades").tail(12)
        draw(px.bar(ranking,x="unidades",y="nombre",orientation="h",labels={"unidades":"Unidades previstas","nombre":""}))
    a,b=st.columns(2)
    with a:
        section("3 · Escenario de existencias","¿Cuándo quedarían unidades sin cubrir si no llegan compras?")
        if daily.empty:
            st.info("El horizonte no contiene días posteriores a hoy. Actualiza la fecha de corte con un registro completo para simular stock futuro.")
        else:
            labels=dict(zip(daily.producto_id,daily.nombre))
            pid=st.selectbox("Producto del escenario",list(labels),format_func=labels.get,key="scenario_product")
            view=daily.loc[daily.producto_id.eq(pid)]
            fig=px.line(view,x="fecha",y="saldo_sin_entradas",markers=True,labels={"saldo_sin_entradas":"Saldo teórico (u.)","fecha":"Día"})
            fig.add_hline(y=0,line_dash="dash",line_color="#b65f4d")
            draw(fig)
            st.caption("Un saldo negativo representa unidades previstas que el stock no cubriría; no es stock físico negativo ni probabilidad de quiebre.")
    with b:
        section("4 · Ingreso orientativo por día","¿Qué importe implicaría vender las unidades previstas al precio actual?")
        byday=future.groupby("fecha",as_index=False).ingreso_orientativo.sum()
        draw(px.bar(byday,x="fecha",y="ingreso_orientativo",color_discrete_sequence=[COLORS[1]],labels={"fecha":"Día proyectado","ingreso_orientativo":"S/ orientativos"}))
    if not scenario.empty:
        section("Reposición bajo el escenario","Compra orientativa para cubrir el horizonte restante y conservar el mínimo; requiere revisión.")
        table(scenario,"bi_escenario_reposicion.csv")
        st.caption("Usa solo días futuros respecto a hoy en Lima. No descuenta pedidos pendientes ni reconstruye el stock al corte de un pronóstico antiguo. No sustituye la decisión de compra del módulo Reposición.")
    with st.expander("Detalle de la proyección y patrón por día de semana"):
        table(future,"bi_pronostico_detallado.csv")
        days=future.groupby("fecha",as_index=False).unidades.sum()
        days["dia_semana"]=days.fecha.dt.dayofweek.map(dict(enumerate(["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"])))
        pattern=days.groupby("dia_semana",as_index=False).unidades.mean()
        draw(px.bar(pattern,x="dia_semana",y="unidades",labels={"unidades":"Promedio previsto por día"}))
        st.caption("Promedio de los días que aparecen en el horizonte, no suma de semanas de distinta duración.")


def _saved(repo,products,today):
    data=repo.table("bodega_predicciones")
    if data.empty:st.info("Todavía no hay pronósticos guardados. Evalúa un producto y guarda su proyección.");return
    data=data.copy()
    for col in ["fecha","corte"]:data[col]=pd.to_datetime(data[col])
    for col in ["unidades","wape_validacion","wape_baseline"]:data[col]=pd.to_numeric(data[col],errors="coerce")
    data=data.merge(products[["id","nombre","categoria","precio"]],left_on="producto_id",right_on="id",how="left")
    data["ingreso_orientativo"]=data.unidades*data.precio
    a,b,c=st.columns(3)
    cats=a.multiselect("Categorías de la proyección",sorted(data.categoria.dropna().unique()),key="saved_forecast_categories")
    labels=dict(zip(data.producto_id,data.nombre))
    ids=b.multiselect("Productos guardados",list(labels),format_func=labels.get,key="saved_forecast_ids")
    methods=c.multiselect("Métodos",sorted(data.metodo.unique()),key="saved_forecast_methods")
    for values,col in [(cats,"categoria"),(ids,"producto_id"),(methods,"metodo")]:
        if values:data=data.loc[data[col].isin(values)]
    mode=st.radio("Cortes a consultar",["Último corte de cada producto","Elegir un corte"],horizontal=True)
    if data.empty:st.info("No hay predicciones para estos filtros.");return
    if mode.startswith("Último"):
        newest=data.groupby("producto_id",as_index=False).corte.max()
        data=data.merge(newest,on=["producto_id","corte"])
    else:
        cut=st.selectbox("Corte guardado",sorted(data.corte.dt.date.unique(),reverse=True))
        data=data.loc[data.corte.eq(pd.Timestamp(cut))]
    st.caption("Cada producto aporta un solo corte. Si los cortes son distintos, sus horizontes pueden tener longitudes diferentes; no se mezclan como una evaluación homogénea.")
    _plots(data,products,today)
    table(data[["producto_id","nombre","categoria","fecha","corte","unidades","metodo","wape_validacion","wape_baseline"]],"bi_pronosticos_guardados.csv")


def render(repo,products,sales,role,today,notify,embedded=False):
    if embedded:section("Proyecciones de la bodega","Unidades previstas, comparación de métodos y escenarios de existencias.")
    else:page_header("Pronóstico que se puede comprobar","Proyecciones por producto, comparación de métodos y escenarios de existencias para decidir con contexto.")
    if products.empty or sales.empty:st.info("Primero carga productos e historial.");return
    mode=st.radio("Vista de predicciones",["Evaluar y proyectar","Pronósticos guardados"],horizontal=True,key="forecast_view")
    if mode=="Pronósticos guardados":_saved(repo,products,today);return
    st.caption("Esta página tiene su propio período de entrenamiento. Los filtros comerciales de las otras páginas BI no recortan el historial del modelo.")
    ids=products.id.tolist();labels=dict(zip(products.id,products.nombre))
    chosen=st.multiselect("Productos a pronosticar",ids,default=ids[:1],max_selections=20,format_func=labels.get,key="forecast_products")
    a,b,c=st.columns(3)
    start=a.date_input("Inicio del registro completo",value=sales.fecha.min().date(),key="forecast_start")
    end=b.date_input("Fecha de corte",value=sales.fecha.max().date(),max_value=today,key="forecast_end")
    horizon=c.selectbox("Días a pronosticar",[7,14,28],key="forecast_horizon")
    complete=st.checkbox("Confirmo que cada día del período tiene registro completo; un día sin líneas significa cero ventas.",key="forecast_complete")
    stockout=st.checkbox("Hubo faltantes o días con ventas sin registrar",key="forecast_stockout")
    if stockout:st.warning("Corrige o delimita el registro antes de evaluar: las ventas realizadas no miden la demanda perdida por faltantes.")
    if not complete or stockout:st.info("Confirma la cobertura del registro para evaluar el pronóstico.");return
    if not chosen:st.info("Elige al menos un producto.");return
    if start>end:st.info("La fecha inicial debe preceder al corte.");return
    selected=sales.loc[sales.producto_id.isin(chosen)&sales.fecha.between(pd.Timestamp(start),pd.Timestamp(end))]
    digest=hashlib.sha256(pd.util.hash_pandas_object(selected[["producto_id","fecha","cantidad"]],index=False).values.tobytes()).hexdigest()
    meta=products.loc[products.id.isin(chosen),["id","precio","categoria","nombre"]].to_csv(index=False)
    signature=(tuple(chosen),str(start),str(end),horizon,digest,meta)
    if st.button("Evaluar y pronosticar",type="primary"):
        with st.spinner("Comparando métodos con semanas reservadas…"):
            result=evaluate_portfolio(sales,products,chosen,start,end,horizon)
        st.session_state["portfolio_result"]=(signature,result)
        notify(repo,"pronostico_evaluado")
    stored=st.session_state.get("portfolio_result")
    if not stored or stored[0]!=signature:return
    result=stored[1]
    if not result["errors"].empty:
        st.warning("Algunos productos no pudieron evaluarse con este registro.")
        st.dataframe(result["errors"],hide_index=True,width="stretch")
    future=result["future"]
    if future.empty:return
    st.caption(f"Corte {end:%d/%m/%Y} · proyección {future.fecha.min():%d/%m/%Y} al {future.fecha.max():%d/%m/%Y}. Son estimaciones, no ventas realizadas.")
    _plots(future,products,today)
    section("Validación temporal de los métodos","Últimos 28 días reservados después de un mínimo de 56 días de entrenamiento.")
    score=validation_wape(result["validation"])
    a,b=st.columns(2)
    a.metric("WAPE del portafolio elegido",f"{100*score:.1f}%" if score is not None else "—")
    b.metric("Días de validación por producto",28)
    comparison=result["validation"].groupby("fecha",as_index=False)[["observado","baseline","Random Forest","elegido"]].sum()
    draw(px.line(comparison,x="fecha",y=["observado","baseline","Random Forest","elegido"],labels={"value":"Unidades","fecha":"Día reservado","variable":"Serie"}))
    methods=result["methods"].copy();methods["WAPE %"]=100*methods.pop("WAPE")
    table(methods,"bi_evaluacion_metodos.csv")
    st.caption("WAPE = suma de errores absolutos / suma de unidades observadas. Menor es mejor; no se fuerza una precisión mínima. El portafolio pondera por unidades observadas. Cada artículo elige Random Forest solo si supera al mejor método sencillo. Este bloque selecciona el método: es validación preliminar, no una prueba final independiente ni un intervalo de confianza.")
    if role in {"administrador","analista"} and st.button("Guardar evaluación y pronóstico"):
        repo.save_forecast(saved_records(future));notify(repo,"pronostico_guardado");st.success("Pronóstico guardado.")
