from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def app(monkeypatch):
    monkeypatch.chdir(ROOT); monkeypatch.setenv("APP_MODE","demo")
    return AppTest.from_file(ROOT/"app.py",default_timeout=45).run()


def test_all_pages_render(app):
    assert not app.exception
    for page in ["Resumen BI","Registrar venta","Historial de ventas","Fiados","Inventario","Reposición","Pronóstico","Importar historial","Actividad y datos"]:
        app.radio(key="page").set_value(page).run()
        assert not app.exception
        assert not app.error


def test_register_sale_through_ui(app):
    app.radio(key="page").set_value("Registrar venta").run()
    repo=app.session_state["demo_repo"]; before=repo.products[0]["stock"]
    app.button(key="add_1").click().run()
    # AppTest no reproduce los reruns de fragmentos de un diálogo nativo.
    # El recorrido del drawer se comprueba además en Chromium.
    app.session_state["shop_view"]="carrito"
    app.run()
    app.button(key="plus_checkout_1").click().run()
    app.radio(key="sale_payment").set_value("Plin").run()
    app.text_input(key='payment_reference').set_value('TEST-001').run()
    app.checkbox(key="payment_received").check().run()
    next(b for b in app.button if b.label=="Confirmar venta").click().run()
    assert not app.exception and not app.error
    assert repo.products[0]["stock"]==before-2
    assert repo.headers[-1]["medio_pago"]=="Plin"
    assert "pending_sale" not in app.session_state
    assert len(app.session_state["cart"])==0


def test_uncertain_sale_retries_same_operation_without_duplicate(app,monkeypatch):
    from bodega.repository import DataError
    app.radio(key="page").set_value("Registrar venta").run()
    app.button(key="add_1").click().run()
    app.session_state["shop_view"]="carrito";app.run()
    repo=app.session_state["demo_repo"];before=repo.products[0]["stock"]
    original=repo.sale;calls=[]
    def interrupted(op,items,payment,**kwargs):
        calls.append(op)
        result=original(op,items,payment,**kwargs)
        if len(calls)==1:raise DataError("Sin confirmación",confirmed_rejected=False)
        return result
    monkeypatch.setattr(repo,"sale",interrupted)
    app.checkbox(key="payment_received").check().run()
    next(b for b in app.button if b.label=="Confirmar venta").click().run()
    assert "pending_sale" in app.session_state
    app.run()
    next(b for b in app.button if b.label=="Reintentar venta pendiente").click().run()
    assert not app.exception and not app.error
    assert len(calls)==2 and calls[0]==calls[1]
    assert repo.products[0]["stock"]==before-1
    assert "pending_sale" not in app.session_state


def test_payment_must_be_confirmed_and_resets_when_cart_or_method_changes(app):
    app.radio(key="page").set_value("Registrar venta").run()
    app.button(key="add_1").click().run()
    app.session_state["shop_view"]="carrito";app.run()
    repo=app.session_state["demo_repo"];stock=repo.products[0]["stock"];sales=len(repo.headers)
    confirm=lambda:next(b for b in app.button if b.label=="Confirmar venta")
    assert confirm().disabled
    from streamlit.testing.v1.errors import AppTestError
    with pytest.raises(AppTestError):confirm().click()
    assert len(repo.headers)==sales and repo.products[0]["stock"]==stock
    app.run()
    app.checkbox(key="payment_received").check().run()
    assert not confirm().disabled
    app.button(key="plus_checkout_1").click().run()
    assert not app.checkbox(key="payment_received").value and confirm().disabled
    app.checkbox(key="payment_received").check().run()
    app.radio(key="sale_payment").set_value("Plin").run()
    assert not app.checkbox(key="payment_received").value and confirm().disabled
    app.text_input(key='payment_reference').set_value('TEST-002').run()
    app.checkbox(key="payment_received").check().run()
    next(i for i in app.number_input if i.label=="Descuento S/").set_value(.2).run()
    assert not app.checkbox(key="payment_received").value and confirm().disabled
    assert len(repo.headers)==sales and repo.products[0]["stock"]==stock


def test_catalog_filters_and_product_information(app):
    app.radio(key="page").set_value("Registrar venta").run()
    app.text_input(key="catalog_search").set_value("7750001000011").run()
    assert len([x for x in app.button if str(x.key).startswith("detail_")])==1
    app.button(key="detail_1").click().run()
    assert not app.exception
    assert [x.label for x in app.expander]==["INFORMACIÓN DEL PRODUCTO"]


def test_forecast_evaluate_and_persist_through_ui(app):
    app.radio(key="page").set_value("Pronóstico").run()
    app.checkbox[0].set_value(True).run()
    next(b for b in app.button if b.label=="Evaluar y pronosticar").click().run()
    assert not app.exception and not app.error
    next(b for b in app.button if b.label=="Guardar evaluación y pronóstico").click().run()
    assert len(app.session_state["demo_repo"].predictions)==7
    app.radio(key="forecast_view").set_value("Pronósticos guardados").run()
    assert not app.exception and not app.error


def test_cloud_never_falls_back_to_demo(monkeypatch):
    monkeypatch.chdir(ROOT);monkeypatch.setenv("APP_MODE","cloud")
    app=AppTest.from_file(ROOT/"app.py").run()
    assert not app.exception
    assert any(x.label=="Correo" for x in app.text_input)
    assert "demo_repo" not in app.session_state


def test_home_quick_action_and_replenishment_decision(app):
    next(b for b in app.button if b.label=="Ver reposición sugerida").click().run()
    assert app.radio(key="page").value=="Reposición"
    next(i for i in app.text_input if i.label=="Motivo de tu decisión").set_value("Comprar mañana")
    next(b for b in app.button if b.label=="Guardar decisión").click().run()
    assert not app.exception and not app.error
    assert len(app.session_state["demo_repo"].decisions)==1


def test_all_bi_pages_olap_operations_and_dw_tables(app):
    from bodega.bi_pages import PAGES
    app.radio(key="page").set_value("Resumen BI").run()
    for page in PAGES:
        app.radio(key="bi_page").set_value(page).run()
        assert not app.exception and not app.error
    app.radio(key="bi_page").set_value("Cubo OLAP").run()
    for op in ["Slice","Dice","Drill-down","Roll-up","Cubo y subtotales","Pivot"]:
        app.radio(key="olap_operation").set_value(op).run()
        assert not app.exception and not app.error
    app.radio(key="olap_operation").set_value("Drill-down").run()
    next(r for r in app.radio if r.label=="Jerarquía").set_value("Año → trimestre → mes → día").run()
    next(r for r in app.select_slider if r.label=="Nivel de detalle").set_value("Día").run()
    assert not app.exception and not app.error
    app.radio(key="bi_page").set_value("Datos y uso").run()
    for option in app.selectbox(key="bi_dw_table").options:
        app.selectbox(key="bi_dw_table").select(option).run()
        assert not app.exception and not app.error
    for area in ["Calidad e importaciones","Uso del sistema"]:
        app.radio(key="bi_data_area").set_value(area).run()
        assert not app.exception and not app.error


def test_gallery_add_another_url_keeps_unsaved_fields_and_saves(app):
    app.radio(key="page").set_value("Inventario").run()
    article=next(x for x in app.selectbox if x.label=="Artículo")
    article.set_value(1).run()
    next(x for x in app.text_area if x.label=="Descripción").set_value("Descripción con dos imágenes")
    app.text_input(key="gallery_url_1_0").set_value("https://example.com/first.png")
    next(b for b in app.button if b.label=="Agregar otra URL de imagen referencial").click().run()
    assert app.text_input(key="gallery_url_1_0").value=="https://example.com/first.png"
    assert next(x for x in app.text_area if x.label=="Descripción").value=="Descripción con dos imágenes"
    app.text_input(key="gallery_url_1_1").set_value("https://example.com/second.png")
    next(b for b in app.button if b.label=="Guardar producto").click().run()
    assert not app.exception and not app.error
    p=app.session_state["demo_repo"].products[0]
    assert p["imagenes_urls"]==["https://example.com/first.png","https://example.com/second.png"]
    assert p["imagen_url"]==p["imagenes_urls"][0]


def test_bi_empty_sales_is_explicit(app):
    from bodega.bi_pages import PAGES
    for h in app.session_state["demo_repo"].headers:h["estado"]="ANULADA"
    app.radio(key="page").set_value("Resumen BI").run()
    for page in PAGES:
        app.radio(key="bi_page").set_value(page).run()
        assert not app.exception and not app.error


def test_bi_filters_survive_prediction_page_and_clear(app):
    app.radio(key="page").set_value("Resumen BI").run()
    app.multiselect(key="_bif_categories").set_value(["Lácteos"]).run()
    app.radio(key="bi_page").set_value("Predicciones").run()
    app.radio(key="bi_page").set_value("Ventas y rentabilidad").run()
    assert app.multiselect(key="_bif_categories").value==["Lácteos"]
    next(b for b in app.button if b.label=="Limpiar filtros").click().run()
    assert app.multiselect(key="_bif_categories").value==[]
    assert not app.exception and not app.error
