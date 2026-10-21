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
    for page in ["Resumen BI","Registrar venta","Inventario","Reposición","Pronóstico","Importar historial","Actividad y datos"]:
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
    app.radio(key="sale_payment").set_value("Yape").run()
    next(b for b in app.button if b.label=="Confirmar venta").click().run()
    assert not app.exception and not app.error
    assert repo.products[0]["stock"]==before-2
    assert repo.headers[-1]["medio_pago"]=="Yape"
    assert "pending_sale" not in app.session_state
    assert len(app.session_state["cart"])==0


def test_uncertain_sale_retries_same_operation_without_duplicate(app,monkeypatch):
    from bodega.repository import DataError
    app.radio(key="page").set_value("Registrar venta").run()
    app.button(key="add_1").click().run()
    app.session_state["shop_view"]="carrito";app.run()
    repo=app.session_state["demo_repo"];before=repo.products[0]["stock"]
    original=repo.sale;calls=[]
    def interrupted(op,items,payment):
        calls.append(op)
        result=original(op,items,payment)
        if len(calls)==1:raise DataError("Sin confirmación",confirmed_rejected=False)
        return result
    monkeypatch.setattr(repo,"sale",interrupted)
    next(b for b in app.button if b.label=="Confirmar venta").click().run()
    assert "pending_sale" in app.session_state
    app.run()
    next(b for b in app.button if b.label=="Reintentar venta pendiente").click().run()
    assert not app.exception and not app.error
    assert len(calls)==2 and calls[0]==calls[1]
    assert repo.products[0]["stock"]==before-1
    assert "pending_sale" not in app.session_state


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
