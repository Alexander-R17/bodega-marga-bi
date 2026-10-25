from datetime import datetime,timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo
import pytest
from bodega.demo import DemoRepository
from bodega.repository import DataError
from bodega.credit import account_data


@pytest.mark.parametrize('dni,name,limit',[('123','Nombre',10),('12345678','',10),('12345678','Nombre','NaN'),('12345678','Nombre',-1),('12345678','Nombre','10.001')])
def test_invalid_credit_account(dni,name,limit):
    with pytest.raises(DataError):account_data(dni,name,limit)


def setup_credit():
    r=DemoRepository();r.configure_credit('12345678','Cliente prueba',20,True)
    due=datetime.now(ZoneInfo('America/Lima')).date()+timedelta(days=7)
    payload={'op':str(uuid4()),'items':[{'producto_id':1,'cantidad':2,'descuento':0}], 'account':1,'due':due,'total':'9.60'}
    return r,payload


def test_credit_sale_payment_retry_and_no_double_revenue():
    r,p=setup_credit();stock=r.products[0]['stock'];sales=len(r.headers)
    first=r.credit_sale(**p);assert r.credit_sale(**p)==first
    assert r.products[0]['stock']==stock-2 and len(r.headers)==sales+1
    assert r.receipt(first['venta_id'])['pago_confirmado_en'] is None
    op=str(uuid4());r.credit_payment(op,first['venta_id'],'3','Efectivo');r.credit_payment(op,first['venta_id'],'3','Efectivo')
    assert len(r.headers)==sales+1 and r.products[0]['stock']==stock-2
    assert Decimal(r.credit_overview()['cuentas'][0]['saldo'])==Decimal('6.60')
    assert Decimal(r.receipt(first['venta_id'])['fiado_saldo'])==Decimal('6.60')
    summary=r.credit_summary(datetime.now(ZoneInfo('America/Lima')).date(),datetime.now(ZoneInfo('America/Lima')).date())
    assert Decimal(summary['credito_periodo'])==Decimal('9.60') and Decimal(summary['abonos_periodo'])==3


def test_credit_limit_overpayment_and_paid_sale_annul_protection():
    r,p=setup_credit();sale=r.credit_sale(**p);stock=r.products[0]['stock'];count=len(r.headers)
    with pytest.raises(DataError,match='Límite'):r.credit_sale(**{**p,'op':str(uuid4()),'total':'14.40','items':[{'producto_id':1,'cantidad':3,'descuento':0}]})
    assert r.products[0]['stock']==stock and len(r.headers)==count
    with pytest.raises(DataError,match='supera'):r.credit_payment(str(uuid4()),sale['venta_id'],10,'Efectivo')
    op=str(uuid4());r.credit_payment(op,sale['venta_id'],3,'Efectivo')
    with pytest.raises(DataError,match='Anula primero'):r.annul(str(uuid4()),sale['venta_id'],'Error caja')
    r.reverse_credit_payment(op,'Error de registro');r.reverse_credit_payment(op,'Error de registro')
    r.annul(str(uuid4()),sale['venta_id'],'Error caja')
    assert Decimal(r.credit_overview()['cuentas'][0]['saldo'])==0


def test_blocked_credit_can_still_receive_payment_and_refs_are_unique():
    r,p=setup_credit();sale=r.credit_sale(**p)
    r.configure_credit('12345678','Cliente prueba',20,False)
    with pytest.raises(DataError,match='bloqueada'):r.credit_sale(**{**p,'op':str(uuid4())})
    r.credit_payment(str(uuid4()),sale['venta_id'],1,'Yape','REF-0001','YAPE')
    with pytest.raises(DataError,match='Referencia'):r.credit_payment(str(uuid4()),sale['venta_id'],1,'Yape','ref-0001','yape')
    with pytest.raises(DataError,match='Referencia'):r.sale(str(uuid4()),[{'producto_id':1,'cantidad':1,'descuento':0}],
        'Yape',confirmed_total=4.8,reference='REF-0001',entity='YAPE')


def test_credit_ticket_does_not_claim_cash_paid():
    import fitz
    from bodega.receipts import receipt_pdf
    r,p=setup_credit();sale=r.credit_sale(**p)
    with fitz.open(stream=receipt_pdf(r.receipt(sale['venta_id'])),filetype='pdf') as pdf:
        text='\n'.join(page.get_text() for page in pdf)
    assert 'VENTA A FIADO' in text and 'Pendiente:' in text
    assert 'Pago confirmado manualmente' not in text


def test_credit_checkout_account_payment_and_bi_ui(monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    root=Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root);monkeypatch.setenv('APP_MODE','demo')
    app=AppTest.from_file(root/'app.py',default_timeout=45).run()
    repo=app.session_state['demo_repo'];repo.configure_credit('12345678','Cliente prueba',100,True)
    app.radio(key='page').set_value('Registrar venta').run();app.button(key='add_1').click().run()
    app.session_state['shop_view']='carrito';app.run()
    app.text_input(key='sale_customer_dni').set_value('12345678').run()
    app.text_input(key='sale_customer_name').set_value('Cliente prueba').run()
    app.radio(key='sale_payment').set_value('Fiado').run()
    app.checkbox(key='credit_authorized').check().run()
    next(b for b in app.button if b.label=='Registrar venta a fiado').click().run()
    assert not app.exception and not app.error
    assert repo.headers[-1]['medio_pago']=='Fiado'
    assert app.session_state['cart']==[]
    app.radio(key='page').set_value('Fiados').run()
    next(w for w in app.number_input if w.label=='Importe del abono S/').set_value(3.)
    next(w for w in app.checkbox if w.label=='Comprobé que recibí este abono en efectivo o en la cuenta del negocio').check()
    next(b for b in app.button if b.label=='Guardar abono').click().run()
    assert not app.exception and not app.error
    assert Decimal(repo.credit_overview()['cuentas'][0]['saldo'])==Decimal('1.80')
    app.radio(key='page').set_value('Resumen BI').run()
    app.radio(key='bi_page').set_value('Fiados y cobranza').run()
    assert not app.exception and not app.error
    assert any(m.label=='Abonos recibidos · período' and '3.00' in str(m.value) for m in app.metric)


def test_wait_dialog_detects_without_selling_until_review(monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    import bodega.charge_wait as wait
    root=Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root);monkeypatch.setenv('APP_MODE','demo');monkeypatch.setattr(wait,'enabled',lambda:True)
    device='11111111-1111-4111-8111-111111111111';state=['ESPERANDO'];order={}
    monkeypatch.setattr(DemoRepository,'receivers',lambda self:[{'id':device,'nombre':'Receptor local','activo':True}],raising=False)
    def start(self,op,device,items,customer,total):
        order.update(id=op,items=items,customer=customer,total=total);return {'id':op}
    def status(self,op):return {'id':op,'estado':state[0],'importe_centimos':480,'segundos_restantes':90,'venta_id':None}
    def finish(self,op,*,cancel=False,reference='',entity='',reviewed=False):
        if cancel:return {'estado':'CANCELADO'}
        assert reviewed
        return self.sale(op,order['items'],'Yape',confirmed_total=order['total'],customer=order['customer'],reference=reference,entity=entity)
    monkeypatch.setattr(DemoRepository,'start_charge',start,raising=False)
    monkeypatch.setattr(DemoRepository,'charge_status',status,raising=False)
    monkeypatch.setattr(DemoRepository,'finish_charge',finish,raising=False)
    app=AppTest.from_file(root/'app.py',default_timeout=45).run()
    app.radio(key='page').set_value('Registrar venta').run();app.button(key='add_1').click().run()
    app.session_state['shop_view']='carrito';app.run();app.radio(key='sale_payment').set_value('Yape').run()
    repo=app.session_state['demo_repo'];before=len(repo.headers)
    app.button(key='charge_start').click().run()
    assert not app.exception
    assert 'active_charge' in app.session_state
    assert any('Tiempo restante:' in t.value for t in app.caption)
    state[0]='DETECTADO';app.run()
    assert not app.exception and len(repo.headers)==before
    commit=next(b for b in app.button if b.label=='Confirmar abono y registrar venta')
    assert commit.disabled
    next(t for t in app.text_input if t.label=='Código de operación del abono').set_value('UI-TEST-0001').run()
    next(c for c in app.checkbox if c.label=='Revisé el movimiento y recibí el importe completo de este cliente').check().run()
    next(b for b in app.button if b.label=='Confirmar abono y registrar venta').click().run()
    assert not app.exception and len(repo.headers)==before+1
    assert 'active_charge' not in app.session_state and app.session_state['cart']==[]
