"""Hechos, agregaciones y OLAP. Tickets y porcentajes se recalculan desde el grano."""
from itertools import combinations
import numpy as np
import pandas as pd
from bodega.analytics import prepare_sales, replenish

WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MONTHS = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIMENSIONS = {"Año":"anio", "Trimestre":"trimestre", "Mes":"periodo_mes", "Día":"periodo_dia",
    "Día de semana":"dia_semana", "Categoría":"categoria", "Producto":"producto", "Proveedor":"proveedor",
    "Medio de pago":"medio_pago", "Origen":"origen"}
MEASURES = {"Ventas S/":"ventas", "Unidades":"unidades", "Margen bruto S/":"margen_bruto",
    "Tickets únicos":"tickets", "Ticket promedio S/":"ticket_promedio", "Margen bruto %":"margen_porcentaje"}


def facts(data):
    df = prepare_sales(data)
    for name in ["proveedor", "codigo", "id_detalle", "descuento"]:
        if name not in df: df[name] = 0 if name in {"id_detalle", "descuento"} else "Sin dato"
    df["fecha"] = pd.to_datetime(df.fecha).dt.normalize()
    df["anio"] = df.fecha.dt.year
    df["mes"] = df.fecha.dt.month
    df["trimestre"] = df.fecha.dt.to_period("Q").astype(str)
    df["periodo_mes"] = df.fecha.dt.strftime("%Y-%m")
    df["periodo_dia"] = df.fecha.dt.strftime("%Y-%m-%d")
    df["dia_semana_num"] = df.fecha.dt.dayofweek + 1
    df["dia_semana"] = df.fecha.dt.dayofweek.map(dict(enumerate(WEEKDAYS)))
    df["producto"] = df.codigo.astype(str) + " · " + df.nombre.astype(str)
    # Una fecha histórica sin hora no se convierte en una venta a medianoche.
    stamp = pd.to_datetime(df.get("fecha_hora", pd.Series(index=df.index,dtype=object)), utc=True, errors="coerce",format="mixed")
    df["hora"] = stamp.dt.tz_convert("America/Lima").dt.hour.where(df.origen.eq("POS"))
    return df


def apply_filters(df, filters):
    out = df.copy()
    dates = filters.get("dates")
    if dates and len(dates) == 2:
        out = out.loc[out.fecha.between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))]
    for option, column in [("years","anio"),("months","mes"),("categories","categoria"),
        ("products","producto_id"),("suppliers","proveedor"),("payments","medio_pago"),("origins","origen")]:
        selected = filters.get(option, [])
        if selected: out = out.loc[out[column].isin(selected)]
    return out


def filter_products(products, filters):
    result=products.copy()
    for option,column in [("categories","categoria"),("products","id"),("suppliers","proveedor")]:
        if filters.get(option): result=result.loc[result[column].isin(filters[option])]
    return result


def aggregate(df, dimensions=()):
    dims=list(dict.fromkeys(dimensions))
    if df.empty:
        if dims: return pd.DataFrame(columns=dims+["ventas","unidades","margen_bruto","tickets","lineas","descuentos","costo","ticket_promedio","margen_porcentaje"])
        result=pd.DataFrame([dict(ventas=0.,unidades=0.,margen_bruto=0.,tickets=0,lineas=0,descuentos=0.)])
    elif dims:
        result=df.groupby(dims,dropna=False,observed=True,as_index=False).agg(
            ventas=("ingreso","sum"),unidades=("cantidad","sum"),margen_bruto=("margen_bruto","sum"),
            tickets=("venta_id","nunique"),lineas=("venta_id","size"),descuentos=("descuento","sum"))
    else:
        result=pd.DataFrame([dict(ventas=df.ingreso.sum(),unidades=df.cantidad.sum(),margen_bruto=df.margen_bruto.sum(),
            tickets=df.venta_id.nunique(),lineas=len(df),descuentos=df.descuento.sum())])
    result["costo"]=result.ventas-result.margen_bruto
    result["ticket_promedio"]=result.ventas.div(result.tickets.replace(0,np.nan))
    result["margen_porcentaje"]=100*result.margen_bruto.div(result.ventas.replace(0,np.nan))
    return result


def pivot(df, row, column, measure):
    if row==column: raise ValueError("Elige dimensiones diferentes para filas y columnas.")
    if df.empty: return pd.DataFrame()
    cells=aggregate(df,[row,column])
    table=cells.pivot(index=row,columns=column,values=measure)
    total_label="TOTAL"
    while total_label in set(df[row].dropna())|set(df[column].dropna()):total_label+=" GENERAL"
    if measure not in {"ticket_promedio","margen_porcentaje"}: table=table.fillna(0)
    totals_row=aggregate(df,[row]).set_index(row)[measure]
    table[total_label]=totals_row
    total_column=aggregate(df,[column]).set_index(column)[measure]
    table.loc[total_label]=[aggregate(df)[measure].iloc[0] if c==total_label else total_column.get(c,np.nan) for c in table.columns]
    table.attrs["total_label"]=total_label
    return table


def cube(df, dimensions):
    dims=list(dict.fromkeys(dimensions))
    if len(dims)>3: raise ValueError("Selecciona hasta tres dimensiones para mostrar todos los subtotales.")
    rows=[]
    for size in range(len(dims)+1):
        for subset in combinations(dims,size):
            part=aggregate(df,subset)
            mask=0
            for i,dim in enumerate(dims):
                if dim not in subset:
                    part[dim]="TOTAL";mask+=1<<(len(dims)-i-1)
            part["mascara_agrupacion"]=mask
            rows.append(part)
    result=pd.concat(rows,ignore_index=True)
    result.insert(0,"id",range(1,len(result)+1))
    return result


def product_ranking(df):
    if df.empty:return aggregate(df,["producto_id","producto","categoria"])
    result=aggregate(df,["producto_id","producto","categoria"]).sort_values("ventas",ascending=False)
    total=result.ventas.sum()
    result["participacion_pct"]=100*result.ventas/total if total>0 else 0.
    result["acumulado_pct"]=result.participacion_pct.cumsum()
    before=result.acumulado_pct-result.participacion_pct
    result["clase_abc"]=np.where(total<=0,"Sin venta",np.where(before<80,"A",np.where(before<95,"B","C")))
    return result


def inventory(products, sales, today, coverage=7):
    result=replenish(products,sales,today,coverage)
    if result.empty:return result
    result["cobertura_dias"]=result.stock.div(result.unidades_dia.replace(0,np.nan))
    result["valor_costo"]=result.stock*result.costo
    result["margen_unitario"]=result.precio-result.costo
    result["prioridad"]=np.where(result.stock.eq(0),"Agotado",
        np.where((result.stock<=result.stock_minimo)|(result.cobertura_dias<result.plazo_dias),"Prioritario","Disponible"))
    return result


def ordered_funnel(events):
    steps=["catalogo_abierto","carrito_agregado","caja_abierta","venta_confirmada"]
    labels=["Catálogo abierto","Producto agregado","Caja abierta","Venta confirmada"]
    counts=[0]*4
    if not events.empty and {"sesion_id","fecha_hora","evento"}.issubset(events):
        data=events.dropna(subset=["sesion_id"]).copy()
        data["fecha_hora"]=pd.to_datetime(data.fecha_hora,utc=True,errors="coerce",format="mixed")
        for _,group in data.dropna(subset=["fecha_hora"]).groupby("sesion_id"):
            previous=None
            for i,step in enumerate(steps):
                times=group.loc[group.evento.eq(step),"fecha_hora"]
                if previous is not None:times=times.loc[times>=previous]
                if times.empty:break
                previous=times.min();counts[i]+=1
    return pd.DataFrame({"Etapa":labels,"Sesiones":counts})
