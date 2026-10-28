from datetime import datetime,timezone,timedelta
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from bodega.checkout import customer_data
from bodega.repository import DataError
from bodega.charge_wait import receiver_ready

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('dni',['Alexander','1234567','123456789','１２３４５６７８','1234 678','1234e678'])
def test_invalid_dni_never_reaches_a_sale(dni):
    with pytest.raises(DataError):customer_data({'dni':dni,'nombre':'Alexander'})

def test_dni_preserves_leading_zero_and_rejects_name_numbers():
    assert customer_data({'dni':'01234567','nombre':'María O’Connor'})['dni']=='01234567'
    with pytest.raises(DataError):customer_data({'dni':'12345678','nombre':'1234'})

def test_receiver_requires_contact_instead_of_only_pairing():
    assert not receiver_ready({'activo':True,'ultimo_contacto':None})
    assert not receiver_ready({'activo':False,'ultimo_contacto':datetime.now(timezone.utc).isoformat()})
    assert not receiver_ready({'activo':True,'ultimo_contacto':(datetime.now(timezone.utc)-timedelta(minutes=21)).isoformat()})
    assert receiver_ready({'activo':True,'ultimo_contacto':datetime.now(timezone.utc).isoformat()})

def open_cart(monkeypatch):
    monkeypatch.chdir(ROOT);monkeypatch.setenv('APP_MODE','demo')
    app=AppTest.from_file(ROOT/'app.py',default_timeout=45).run()
    app.radio(key='page').set_value('Registrar venta').run();app.button(key='add_1').click().run()
    app.session_state['shop_view']='carrito';return app.run()

def test_existing_credit_client_selects_name_and_dni_for_cash_sale(monkeypatch):
    app=open_cart(monkeypatch);repo=app.session_state['demo_repo']
    repo.configure_credit('01234567','Alexander prueba',100,True);app.run()
    app.selectbox(key='sale_registered_customer').select('01234567').run()
    assert not any(t.key in {'sale_customer_dni','sale_customer_name'} for t in app.text_input)
    app.checkbox(key='payment_received').check().run()
    next(b for b in app.button if b.label=='Confirmar venta').click().run()
    assert not app.exception and not app.error
    assert repo.headers[-1]['cliente_nombre']=='Alexander prueba' and repo.headers[-1]['cliente_dni']=='01234567'

def test_yape_does_not_allow_manual_or_fake_payment_without_mobile(monkeypatch):
    app=open_cart(monkeypatch);repo=app.session_state['demo_repo'];before=len(repo.headers)
    app.radio(key='sale_payment').set_value('Yape').run()
    assert app.button(key='charge_start').disabled
    assert not any(t.key=='payment_reference' for t in app.text_input)
    assert not any(c.key=='payment_received' for c in app.checkbox)
    assert len(repo.headers)==before

def test_invalid_dni_disables_cash_confirmation_even_if_ui_is_bypassed(monkeypatch):
    app=open_cart(monkeypatch)
    app.text_input(key='sale_customer_dni').set_value('Alejandr').run()
    assert app.error
    assert next(b for b in app.button if b.label=='Confirmar venta').disabled
