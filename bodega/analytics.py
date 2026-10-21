import math
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor


def prepare_sales(df):
    if df.empty:
        return pd.DataFrame(columns=["fecha", "venta_id", "producto_id", "nombre", "categoria",
            "cantidad", "ingreso", "margen_bruto", "medio_pago", "origen"])
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    for col in ["cantidad", "ingreso", "margen_bruto", "precio_unitario", "costo_unitario", "descuento"]:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="raise")
    return df


def enrich_products(products, categories, suppliers):
    if products.empty:
        return products
    df = products.copy()
    for col in ["precio", "costo", "stock", "stock_minimo", "plazo_dias"]:
        df[col] = pd.to_numeric(df[col], errors="raise")
    df = df.merge(categories.rename(columns={"id": "categoria_id", "nombre": "categoria"}), on="categoria_id")
    df = df.merge(suppliers.rename(columns={"id": "proveedor_id", "nombre": "proveedor"}), on="proveedor_id")
    for field in ["descripcion", "marca", "presentacion", "imagen_url"]:
        if field not in df:
            df[field] = ""
        else:
            df[field] = df[field].fillna("").astype(str)
    if "imagenes_urls" not in df:
        df["imagenes_urls"] = [[] for _ in range(len(df))]
    return df


def kpis(sales):
    revenue = float(sales["ingreso"].sum()) if not sales.empty else 0.0
    tickets = int(sales["venta_id"].nunique()) if not sales.empty else 0
    margin = float(sales["margen_bruto"].sum()) if not sales.empty else 0.0
    return {"ventas": revenue, "tickets": tickets, "ticket_promedio": revenue / tickets if tickets else 0,
            "margen": margin, "margen_pct": margin / revenue * 100 if revenue else None}


def replenish(products, sales, cutoff, coverage=7, lookback=28):
    if products.empty:
        return pd.DataFrame()
    end = pd.Timestamp(cutoff).normalize()
    start = end - pd.Timedelta(days=lookback-1)
    s = sales.loc[(sales["fecha"] >= start) & (sales["fecha"] <= end)]
    units = s.groupby("producto_id")["cantidad"].sum() if not s.empty else pd.Series(dtype=float)
    result = products.loc[products["activo"]].copy()
    result["ventas_28d"] = result["id"].map(units).fillna(0)
    result["unidades_dia"] = result["ventas_28d"] / lookback
    result["objetivo_stock"] = result.apply(lambda r: max(int(r.stock_minimo),
        math.ceil(r.unidades_dia * (r.plazo_dias+coverage))), axis=1)
    result["comprar"] = (result["objetivo_stock"] - result["stock"]).clip(lower=0).astype(int)
    result["estado"] = np.where(result.stock == 0, "Agotado", np.where(result.stock <= result.stock_minimo,
        "Stock bajo", "Disponible"))
    result["motivo"] = result.apply(lambda r:
        f"{r.ventas_28d:g} u. en 28 días; {r.plazo_dias:g} días de entrega + {coverage} de cobertura; mínimo {r.stock_minimo:g}.", axis=1)
    return result.sort_values(["comprar", "stock"], ascending=[False, True])


def wape(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    denom = np.abs(actual).sum()
    return float(np.abs(actual-predicted).sum()/denom) if denom > 0 else None


def daily_series(sales, product_id, start, end):
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    if start > end:
        raise ValueError("La fecha inicial debe preceder al corte")
    s = sales.loc[(sales["producto_id"] == product_id) & (sales["fecha"] >= start) & (sales["fecha"] <= end)]
    grouped = s.groupby("fecha")["cantidad"].sum()
    return grouped.reindex(pd.date_range(start,end,freq="D"),fill_value=0).astype(float)


def _features(history, date):
    return [history[-1], history[-7], history[-14], float(np.mean(history[-7:])),
            float(np.mean(history[-28:])), date.dayofweek, date.month]


def _fit(series):
    values = list(series.values)
    X = [_features(values[:i], series.index[i]) for i in range(28,len(values))]
    y = values[28:]
    model = RandomForestRegressor(n_estimators=80, max_depth=7, min_samples_leaf=3,random_state=42,n_jobs=1)
    model.fit(X,y)
    return model


def _predict(series, days, method, model=None):
    history = list(series.astype(float))
    result = []
    # Recursivo: ninguna observación futura entra a los lags del horizonte evaluado.
    for date in pd.date_range(series.index[-1]+pd.Timedelta(days=1), periods=days):
        if method == "Random Forest":
            value = float(model.predict([_features(history,date)])[0])
        elif method == "Estacional semanal":
            value = float(history[-7])
        else:
            value = float(np.mean(series.iloc[-28:]))
        value = max(value,0)
        history.append(value)
        result.append(value)
    return np.asarray(result)


def forecast(series, horizon=7):
    if not 1 <= horizon <= 28:
        raise ValueError("Horizonte entre 1 y 28 días")
    if len(series)<84:
        raise ValueError("Se necesitan 84 días completos: mínimo 56 de entrenamiento y 28 de evaluación")
    if not np.isfinite(series).all() or (series<0).any():
        raise ValueError("Serie inválida")
    train, test = series.iloc[:-28],series.iloc[-28:]
    if test.sum()<=0:
        raise ValueError("WAPE no es interpretable: las 4 semanas de evaluación no tienen ventas positivas")
    rf = _fit(train)
    methods = ["Promedio móvil 28 días", "Estacional semanal", "Random Forest"]
    scores = {m:wape(test,_predict(train,28,m,rf)) for m in methods}
    baseline = min(methods[:2],key=lambda m:scores[m])
    chosen = "Random Forest" if scores["Random Forest"] < scores[baseline] else baseline
    fitted = _fit(series) if chosen=="Random Forest" else None
    future = _predict(series,horizon,chosen,fitted)
    table = pd.DataFrame({"fecha":pd.date_range(series.index[-1]+pd.Timedelta(days=1),periods=horizon),
                          "unidades":future})
    return {"metodo":chosen,"scores":scores,"baseline":baseline,"wape":scores[chosen],
        "wape_baseline":scores[baseline],"exactitud":100*(1-scores[chosen]),"table":table,
        "comparison":pd.DataFrame({"fecha":test.index,"observado":test.values,
            "baseline":_predict(train,28,baseline),"Random Forest":_predict(train,28,"Random Forest",rf)})}


def csv_export(df):
    df = df.copy()
    # Neutralizar fórmulas al abrir exportaciones en programas de hojas de cálculo.
    for col in df.select_dtypes(include=["object", "string"]):
        df[col] = df[col].map(lambda v: "'"+v if isinstance(v,str) and v.lstrip().startswith(("=","+","-","@")) else v)
    return df.to_csv(index=False).encode("utf-8-sig")
