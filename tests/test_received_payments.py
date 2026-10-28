from pathlib import Path
from uuid import uuid4
import json
import pytest
import requests
from streamlit.testing.v1 import AppTest
from bodega.demo import DemoRepository
from bodega.repository import DataError
import bodega.repository as module

ROOT=Path(__file__).resolve().parents[1]

def cloud(monkeypatch):
    monkeypatch.setattr(module,'setting',lambda k:{'SUPABASE_URL':'https://example.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'sb_secret_TEST_ONLY'}[k])
    monkeypatch.setattr(module,'require_identity',lambda:{'uid':'verified-user'})
    monkeypatch.setattr(module,'require_role',lambda *roles:{'uid':'verified-user'})
    return module.CloudRepository()

def test_ambiguous_dni_error_has_actionable_message_without_remote_details(monkeypatch):
    repo=cloud(monkeypatch);r=requests.Response();r.status_code=400
    r._content=json.dumps({'code':'42702','message':'PRIVATE CLIENT DATA','details':'SECRET VALUE'}).encode()
    monkeypatch.setattr(repo.http,'request',lambda *args,**kwargs:r)
    with pytest.raises(DataError) as exc:repo._request('POST','rpc/bodega_confirmar_cobro_aviso',json={})
    assert '11_correccion_clientes_y_conciliacion.sql' in str(exc.value) and '42702' in str(exc.value)
    assert 'PRIVATE' not in str(exc.value) and 'SECRET' not in str(exc.value)

@pytest.mark.parametrize('code,expected',[('23514','23514'),('PRIVATE-1234567890','')])
def test_unknown_error_only_exposes_a_safe_diagnostic_code(monkeypatch,code,expected):
    repo=cloud(monkeypatch);r=requests.Response();r.status_code=400;r._content=json.dumps({'code':code,'message':'PRIVATE CLIENT DATA'}).encode()
    monkeypatch.setattr(repo.http,'request',lambda *args,**kwargs:r)
    with pytest.raises(DataError) as exc:repo._request('POST','rpc/bodega_confirmar_cobro_aviso',json={})
    assert 'PRIVATE' not in str(exc.value)
    if expected:assert expected in str(exc.value)

def test_recovery_requires_review_and_injects_verified_actor(monkeypatch):
    repo=cloud(monkeypatch);calls=[]
    monkeypatch.setattr(repo,'_request',lambda *args,**kw:calls.append((args,kw)) or {'estado':'REGISTRADO'})
    with pytest.raises(DataError):repo.reconcile_received_charge('op')
    assert not calls
    repo.reconcile_received_charge('op',reviewed=True)
    assert calls[0][0]==('POST','rpc/bodega_conciliar_cobro_recibido')
    assert calls[0][1]['json']=={'p_id':'op','p_revisado':True,'p_usuario':'verified-user'}

class RecoveryDemo(DemoRepository):
    def __init__(self,uncertain=False):
        super().__init__();self.op=str(uuid4());self.calls=[];self.uncertain=uncertain
        self.items=[{'producto_id':1,'cantidad':1,'descuento':0}]
    def pending_received_charges(self):
        return [{'id':self.op,'importe_centimos':480,'creado_en':'2026-01-01T12:00:00Z','estado':'VENCIDO','aviso_id':1,
            'items':self.items,'cliente':'Cliente Prueba'}]
    def reconcile_received_charge(self,op,reviewed=False):
        assert reviewed;self.calls.append(op)
        result=self.sale(op,self.items,'Yape',confirmed_total=4.8,customer={'dni':'12345678','nombre':'Cliente Prueba'},
            reference='AVISO-YAPE-1',entity='YAPE DEL NEGOCIO')
        if self.uncertain and len(self.calls)==1:raise DataError('No se recibió respuesta',confirmed_rejected=False)
        return result

@pytest.mark.parametrize('uncertain',[False,True])
@pytest.mark.parametrize('matching_cart',[False,True])
def test_recovery_ui_requires_review_preserves_order_and_retries_without_duplicates(monkeypatch,uncertain,matching_cart):
    monkeypatch.chdir(ROOT);monkeypatch.setenv('APP_MODE','demo')
    repo=RecoveryDemo(uncertain);before=len(repo.headers);stock=repo.products[0]['stock']
    app=AppTest.from_string("import streamlit as st\nfrom bodega.charge_wait import reconciliation_admin\nreconciliation_admin(st.session_state['test_repo'])",default_timeout=30)
    app.session_state['test_repo']=repo;app.session_state['cart']=repo.items.copy();app.session_state['active_charge']={'id':repo.op if matching_cart else str(uuid4())};app.run()
    app.button(key='received_charges_refresh').click().run()
    assert app.button(key='received_charge_commit').disabled
    app.checkbox(key='received_charge_review_'+repo.op).check().run()
    app.button(key='received_charge_commit').click().run()
    if uncertain:
        assert app.error and app.session_state['cart']
        app.button(key='received_charge_commit').click().run()
    assert not app.exception and not app.error
    assert len(repo.headers)==before+1 and repo.products[0]['stock']==stock-1
    assert len(set(repo.calls))==1
    assert app.session_state['cart']==([] if matching_cart else repo.items)
    assert any('recuperada' in s.value for s in app.success)
