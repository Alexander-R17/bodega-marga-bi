from pathlib import Path
import pandas as pd
import numpy as np
import pytest
from bodega.demo import DemoRepository
from bodega.repository import DataError, CloudRepository
from bodega.analytics import prepare_sales, kpis, wape, forecast, csv_export, daily_series
from bodega.imports import validate_csv, COLUMNS


def test_sale_retry_and_stock():
    repo=DemoRepository()
    before=repo.products[0]["stock"]
    items=[{"producto_id":1,"cantidad":2,"descuento":.2}]
    first=repo.sale("op-1",items,"Yape")
    second=repo.sale("op-1",items,"Yape")
    assert first==second
    assert repo.products[0]["stock"]==before-2
    with pytest.raises(DataError,match="reutilizada"):
        repo.sale("op-1",[{"producto_id":1,"cantidad":1,"descuento":0}],"Yape")


def test_failed_cart_does_not_partially_reduce_stock():
    repo=DemoRepository()
    before=repo.products[0]["stock"]
    with pytest.raises(DataError,match="Stock insuficiente"):
        repo.sale("bad",[{"producto_id":1,"cantidad":1,"descuento":0},
                         {"producto_id":3,"cantidad":1,"descuento":0}],"Efectivo")
    assert repo.products[0]["stock"]==before


def test_annul_is_idempotent_and_excludes_revenue():
    repo=DemoRepository(); before=repo.products[0]["stock"]
    result=repo.sale("sale",[{"producto_id":1,"cantidad":2,"descuento":0}],"Plin")
    repo.annul("annul",result["venta_id"],"Error de caja")
    repo.annul("annul",result["venta_id"],"Error de caja")
    assert repo.products[0]["stock"]==before
    assert result["venta_id"] not in repo.table("bodega_v_ventas").venta_id.values


def test_kpi_uses_unique_ticket_and_weighted_revenue():
    df=pd.DataFrame({"venta_id":[1,1,2],"ingreso":[10,20,6],"margen_bruto":[2,5,1]})
    assert kpis(df)["ticket_promedio"]==18
    assert kpis(df)["margen"]==8


def test_csv_rejects_duplicates_unknown_codes_bad_numbers():
    header=",".join(COLUMNS)+"\n"
    raw=(header+"A,2026-09-01,001,2,3.00,2.00,0,Efectivo\n"
        +"A,2026-09-01,001,2,3.00,2.00,0,Efectivo\n"
        +"B,2026-09-01,999,2,3.00,2.00,0,Efectivo\n"
        +"C,2026-09-01,001,2,NaN,2.00,0,Efectivo\n").encode()
    rows,errors,_=validate_csv(raw,{"001"})
    assert len(rows)==1 and len(errors)==3
    assert rows[0]["codigo"]=="001"


def test_import_history_does_not_change_current_stock():
    repo=DemoRepository()
    before=[p["stock"] for p in repo.products]
    rows=[{"ticket":"NEW-HIST-1","fecha":"2026-09-01","codigo":repo.products[0]["codigo"],
        "cantidad":100,"precio_unitario":"4.80","costo_unitario":"3.60","descuento":"0","medio_pago":"Efectivo"}]
    repo.create_batch("b","test.csv","a"*64,rows)
    repo.process_batch("b");repo.process_batch("b")
    assert [p["stock"] for p in repo.products]==before
    assert len([s for s in repo.sales if s["venta_id"]==repo.headers[-1]["id"]])==1


def test_forecast_temporal_holdout_and_baseline():
    series=pd.Series([5.0]*100,index=pd.date_range("2026-01-01",periods=100))
    r=forecast(series)
    assert r["metodo"]!="Random Forest"  # el empate se resuelve por el método sencillo
    assert r["wape"]==0
    assert r["comparison"].fecha.min()==series.index[-28]
    assert r["table"].fecha.min()>series.index[-1]
    assert len(r["table"])==7


def test_holdout_predictions_do_not_use_future_observations():
    index=pd.date_range("2026-01-01",periods=100)
    s=pd.Series(np.tile(np.arange(1,8),15)[:100],index=index,dtype=float)
    altered=s.copy();altered.iloc[-28:]+=10
    first,second=forecast(s),forecast(altered)
    np.testing.assert_allclose(first["comparison"]["Random Forest"],second["comparison"]["Random Forest"])


def test_wape_zero_and_short_history_are_explicit():
    assert wape([0,0],[1,2]) is None
    with pytest.raises(ValueError,match="84"):
        forecast(pd.Series([2]*60,index=pd.date_range("2026-01-01",periods=60)))


def test_export_neutralizes_spreadsheet_formula():
    out=csv_export(pd.DataFrame({"nombre":["=SUM(A1)"," normal","@cmd"]})).decode("utf-8-sig")
    assert "'=SUM" in out and "'@cmd" in out


def test_pagination_reads_all_pages(monkeypatch):
    import bodega.repository as module
    monkeypatch.setattr(module,"setting",lambda key:"https://example.supabase.co" if key=="SUPABASE_URL" else "test")
    repo=CloudRepository()
    calls=[]
    def request(method,path,**kwargs):
        offset=kwargs["params"]["offset"];calls.append(offset)
        return [{"id":i} for i in range(offset,min(offset+300,1050))]
    monkeypatch.setattr(repo,"_request",request)
    assert len(repo.table("bodega_productos"))==1050
    assert calls==[0,300,600,900,1050]


def test_firebase_role_requires_verified_assigned_email(monkeypatch):
    import bodega.auth as module
    monkeypatch.setattr(module,"setting",lambda *args:{"owner@test.com":"administrador"})
    assert module.role_for({"email":"Owner@Test.Com","email_verified":True})=="administrador"
    for claims in [{"email":"owner@test.com","email_verified":False},{"email":"other@test.com","email_verified":True}]:
        with pytest.raises(module.AccessError):module.role_for(claims)


def test_replenishment_decision_preserves_stock_and_reason():
    repo=DemoRepository();before=repo.products[0]["stock"]
    repo.decision("decision",1,10,"DESCARTADA","Ya hay un pedido pendiente",{"stock":before})
    repo.decision("decision",1,10,"DESCARTADA","Ya hay un pedido pendiente",{"stock":before})
    assert repo.products[0]["stock"]==before
    assert len(repo.decisions)==1
    assert repo.decisions[0]["motivo"]=="Ya hay un pedido pendiente"
