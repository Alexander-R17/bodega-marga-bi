from datetime import date
import pandas as pd
import numpy as np
import pytest
from bodega import bi
from bodega.media import normalize_urls, product_urls
from bodega.forecasting import stock_scenario, evaluate_portfolio, validation_wape, saved_records
from bodega.demo import DemoRepository
from bodega.analytics import enrich_products,prepare_sales


@pytest.fixture
def facts():
    return bi.facts(pd.DataFrame([
        dict(venta_id=1,producto_id=1,codigo="001",nombre="Arroz",categoria="Abarrotes",proveedor="P1",fecha="2026-10-01",cantidad=2,ingreso=20,margen_bruto=5,medio_pago="Yape",origen="POS",fecha_hora="2026-10-01T18:00:00Z"),
        dict(venta_id=1,producto_id=2,codigo="002",nombre="Leche",categoria="Lácteos",proveedor="P2",fecha="2026-10-01",cantidad=1,ingreso=5,margen_bruto=1,medio_pago="Yape",origen="POS",fecha_hora="2026-10-01T18:00:00Z"),
        dict(venta_id=2,producto_id=1,codigo="001",nombre="Arroz",categoria="Abarrotes",proveedor="P1",fecha="2026-10-02",cantidad=1,ingreso=10,margen_bruto=-1,medio_pago="Efectivo",origen="HISTORICO",fecha_hora="2026-10-02T05:00:00Z")]))


def test_olap_unique_tickets_and_weighted_percentages(facts):
    result=bi.pivot(facts,"categoria","medio_pago","tickets")
    assert result.loc["TOTAL","TOTAL"]==2
    assert result.loc["TOTAL","Yape"]==1
    # Dos categorías comparten ticket: 2 + 1 no se convierten en tres tickets totales.
    assert result.loc["Abarrotes","TOTAL"]==2 and result.loc["Lácteos","TOTAL"]==1
    margin=bi.pivot(facts,"categoria","medio_pago","margen_porcentaje")
    assert margin.loc["TOTAL","TOTAL"]==pytest.approx(100*5/35)
    avg=bi.pivot(facts,"categoria","medio_pago","ticket_promedio")
    assert avg.loc["TOTAL","TOTAL"]==17.5


def test_cube_has_all_levels_without_changing_grand_total(facts):
    result=bi.cube(facts,["periodo_mes","categoria","medio_pago"])
    assert set(result.mascara_agrupacion)==set(range(8))
    total=result.loc[result.mascara_agrupacion.eq(7)].iloc[0]
    assert total.ventas==35 and total.tickets==2
    assert total.margen_bruto==5


def test_pivot_keeps_a_category_named_total(facts):
    facts.loc[facts.categoria.eq("Abarrotes"),"categoria"]="TOTAL"
    result=bi.pivot(facts,"categoria","medio_pago","ventas")
    assert result.loc["TOTAL","Yape"]==20
    assert result.loc["TOTAL GENERAL","TOTAL GENERAL"]==35


def test_slice_dice_filters_intersect_and_unknown_hour_is_not_midnight(facts):
    view=bi.apply_filters(facts,dict(years=[2026],months=[10],categories=["Abarrotes"],payments=["Yape"]))
    assert len(view)==1 and view.iloc[0].ingreso==20
    assert facts.loc[facts.origen.eq("POS"),"hora"].tolist()==[13,13]
    assert facts.loc[facts.origen.eq("HISTORICO"),"hora"].isna().all()
    assert bi.apply_filters(facts,dict(products=[999])).empty


def test_abc_and_no_sales_have_explicit_results(facts):
    ranked=bi.product_ranking(facts)
    assert ranked.iloc[0].producto_id==1 and ranked.iloc[0].clase_abc=="A"
    assert ranked.acumulado_pct.iloc[-1]==pytest.approx(100)
    empty=bi.facts(pd.DataFrame())
    assert bi.aggregate(empty).iloc[0].tickets==0
    assert np.isnan(bi.aggregate(empty).iloc[0].margen_porcentaje)
    assert bi.pivot(empty,"categoria","medio_pago","ventas").empty


def test_urls_preserve_order_legacy_and_reject_invalid_values():
    urls=["https://example.com/a.png","https://example.com/b.png"]
    assert normalize_urls([urls[0],"",urls[1],urls[0]])==urls
    assert product_urls({"imagen_url":urls[0]})==urls[:1]
    assert product_urls({"imagenes_urls":urls,"imagen_url":"https://example.com/old.png"})==urls
    for value in [["http://example.com/a.png"],["https://user:pass@example.com/a.png"],["https://example.com/a b.png"],[None],urls*5]:
        with pytest.raises(ValueError):normalize_urls(value)


def test_stock_projection_uses_only_future_days_and_never_changes_actual_stock():
    products=pd.DataFrame([dict(id=1,nombre="Arroz",stock=5,stock_minimo=2)])
    future=pd.DataFrame([dict(producto_id=1,fecha=pd.Timestamp(d),unidades=q) for d,q in [("2026-10-20",100),("2026-10-22",4),("2026-10-23",3)]])
    daily,summary=stock_scenario(future,products,date(2026,10,21))
    assert daily.saldo_sin_entradas.tolist()==[1,-2]
    assert summary.iloc[0].Compra_escenario==4
    assert summary.iloc[0].Primer_faltante==pd.Timestamp("2026-10-23")
    assert products.iloc[0].stock==5
    assert stock_scenario(future,products,date(2026,11,1))[0].empty


def test_portfolio_keeps_product_cuts_and_validation_weights():
    repo=DemoRepository()
    products=enrich_products(repo.table("bodega_productos"),repo.table("bodega_categorias"),repo.table("bodega_proveedores"))
    sales=prepare_sales(repo.table("bodega_v_ventas"))
    result=evaluate_portfolio(sales,products,[1,4],sales.fecha.min(),sales.fecha.max(),7)
    assert result["errors"].empty and len(result["future"])==14
    assert len(result["methods"])==6 and len(result["validation"])==56
    assert result["future"].fecha.min()>sales.fecha.max()
    records=saved_records(result["future"])
    repo.save_forecast(records);repo.save_forecast(records)
    assert len(repo.predictions)==14
    data=pd.DataFrame(dict(observado=[1,99],elegido=[0,99]))
    assert validation_wape(data)==.01


def test_funnel_counts_ordered_sessions_once_and_ignores_unmeasured_events():
    rows=[dict(sesion_id="one",evento=e,fecha_hora=f"2026-10-21T12:0{i}:00Z") for i,e in enumerate(["catalogo_abierto","carrito_agregado","carrito_agregado","caja_abierta","venta_confirmada"])]
    rows += [dict(sesion_id="two",evento="venta_confirmada",fecha_hora="2026-10-21T12:00:00Z"),dict(sesion_id="two",evento="catalogo_abierto",fecha_hora="2026-10-21T12:01:00Z"),dict(sesion_id=None,evento="catalogo_abierto",fecha_hora="2026-10-21T12:00:00Z")]
    assert bi.ordered_funnel(pd.DataFrame(rows)).Sesiones.tolist()==[2,1,1,1]
