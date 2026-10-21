"""Pronósticos por producto y escenarios derivados; no modelan demanda perdida."""
import math
import numpy as np
import pandas as pd
from bodega.analytics import daily_series, forecast


def evaluate_portfolio(sales, products, product_ids, start, end, horizon):
    if not product_ids or len(product_ids)>20:
        raise ValueError("Selecciona entre 1 y 20 productos por evaluación.")
    if pd.Timestamp(start)>pd.Timestamp(end):raise ValueError("El inicio debe preceder al corte.")
    future=[];validation=[];methods=[];errors=[]
    for pid in dict.fromkeys(product_ids):
        p=products.loc[products.id==pid].iloc[0]
        try:r=forecast(daily_series(sales,int(pid),start,end),horizon)
        except ValueError as exc:
            errors.append({"Producto":p.nombre,"Motivo":str(exc)});continue
        for f in r["table"].itertuples():
            future.append(dict(producto_id=int(pid),nombre=p.nombre,categoria=p.categoria,fecha=f.fecha,
                corte=pd.Timestamp(end),unidades=float(f.unidades),metodo=r["metodo"],
                wape_validacion=r["wape"],wape_baseline=r["wape_baseline"],
                ingreso_orientativo=float(f.unidades)*float(p.precio)))
        comp=r["comparison"].copy()
        comp["elegido"]=comp["Random Forest"] if r["metodo"]=="Random Forest" else comp.baseline
        comp["producto_id"]=int(pid);comp["nombre"]=p.nombre
        validation.append(comp)
        methods.extend(dict(producto_id=int(pid),Producto=p.nombre,Método=m,WAPE=score,
            Elegido=m==r["metodo"]) for m,score in r["scores"].items())
    return dict(future=pd.DataFrame(future),validation=pd.concat(validation,ignore_index=True) if validation else pd.DataFrame(),
        methods=pd.DataFrame(methods),errors=pd.DataFrame(errors))


def stock_scenario(future, products, as_of):
    if future.empty:return pd.DataFrame(),pd.DataFrame()
    data=future.loc[pd.to_datetime(future.fecha)>pd.Timestamp(as_of).normalize()].copy()
    daily=[];summary=[]
    for pid,group in data.groupby("producto_id"):
        p=products.loc[products.id==pid].iloc[0]
        group=group.sort_values("fecha").copy()
        group["saldo_sin_entradas"]=float(p.stock)-group.unidades.cumsum()
        group["stock_disponible"]=group.saldo_sin_entradas.clip(lower=0)
        group["unidades_no_cubiertas"]=(-group.saldo_sin_entradas).clip(lower=0)
        shortage=group.loc[group.saldo_sin_entradas<0,"fecha"]
        suggested=max(0,math.ceil(float(group.unidades.sum())+int(p.stock_minimo)-int(p.stock)))
        summary.append(dict(producto_id=int(pid),Producto=p.nombre,Stock=int(p.stock),
            Unidades_previstas=float(group.unidades.sum()),Compra_escenario=suggested,
            Primer_faltante=shortage.min() if not shortage.empty else pd.NaT,
            Escenario="Faltante proyectado" if not shortage.empty else "Cubierto en el horizonte"))
        daily.append(group)
    return (pd.concat(daily,ignore_index=True) if daily else pd.DataFrame(),pd.DataFrame(summary))


def validation_wape(comparison):
    if comparison.empty or comparison.observado.abs().sum()==0:return None
    return float((comparison.observado-comparison.elegido).abs().sum()/comparison.observado.abs().sum())


def saved_records(future):
    return [dict(producto_id=int(r.producto_id),fecha=pd.Timestamp(r.fecha).date().isoformat(),
        corte=pd.Timestamp(r.corte).date().isoformat(),unidades=round(float(r.unidades),3),metodo=r.metodo,
        wape_validacion=float(r.wape_validacion),wape_baseline=float(r.wape_baseline)) for r in future.itertuples()]
