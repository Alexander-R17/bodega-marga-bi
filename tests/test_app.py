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
    next(b for b in app.button if b.label=="Agregar al carrito").click().run()
    next(b for b in app.button if b.label=="Confirmar venta").click().run()
    assert not app.exception and not app.error
    assert repo.products[0]["stock"]==before-1
    assert "pending_sale" not in app.session_state
    assert len(app.session_state["cart"])==0


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
