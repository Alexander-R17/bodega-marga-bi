from copy import deepcopy
from uuid import uuid4
import pytest
import bodega.shared_cart as shared
from bodega.repository import DataError

class Fake:
    def __init__(self):
        self.cart={'items':[],'revision':0,'estado':'ABIERTO','operacion':None,'catalogo_revision':1};self.ops={};self.fail=False
    def shared_read(self):return deepcopy(self.cart)
    def shared_write(self,op,items,revision):
        if op in self.ops:return deepcopy(self.ops[op])
        if revision!=self.cart['revision']:raise DataError('El carrito cambió en otro dispositivo')
        self.cart.update(items=deepcopy(items),revision=revision+1);self.ops[op]=deepcopy(self.cart)
        if self.fail:self.fail=False;raise DataError('Sin confirmación',confirmed_rejected=False)
        return deepcopy(self.cart)
    def shared_freeze(self,op,revision):
        if revision!=self.cart['revision']:raise DataError('El carrito cambió en otro dispositivo')
        self.cart.update(estado='COBRANDO',operacion=op,revision=revision+1);return deepcopy(self.cart)
    def shared_finish(self,op,cancel=False):
        self.cart.update(estado='ABIERTO',operacion=None,items=self.cart['items'] if cancel else [],revision=self.cart['revision']+1)

@pytest.fixture
def state(monkeypatch):
    values={};monkeypatch.setattr(shared.st,'session_state',values);monkeypatch.setattr(shared,'available',lambda r:True);return values


def test_initial_migration_and_remote_user_cart_are_not_silently_overwritten(state):
    repo=Fake();state['cart']=[{'producto_id':1,'cantidad':1,'descuento':0}]
    shared.sync(repo);assert repo.cart['items']==state['cart']
    state.clear();state['cart']=[{'producto_id':2,'cantidad':1,'descuento':0}]
    shared.sync(repo);assert state['cart']==repo.cart['items']
    assert state['previous_local_cart'][0]['producto_id']==2


def test_unknown_response_retries_same_operation_without_duplicate(state):
    repo=Fake();shared.sync(repo);state['cart']=[{'producto_id':1,'cantidad':1,'descuento':0}];repo.fail=True
    with pytest.raises(DataError):shared.sync(repo)
    pending=deepcopy(state['shared_upload']);assert repo.cart['revision']==1
    shared.sync(repo);assert repo.cart['revision']==1 and len(repo.ops)==1
    assert pending['op'] in repo.ops and 'shared_upload' not in state


def test_concurrent_remote_change_is_loaded_instead_of_overwritten(state):
    repo=Fake();shared.sync(repo)
    repo.shared_write(str(uuid4()),[{'producto_id':2,'cantidad':1,'descuento':0}],0)
    state['cart']=[{'producto_id':1,'cantidad':1,'descuento':0}];shared.sync(repo)
    assert state['cart'][0]['producto_id']==2 and 'otro dispositivo' in state['shared_notice']


def test_pending_payment_does_not_publish_or_replace_its_snapshot(state):
    repo=Fake();shared.sync(repo);state['pending_sale']={'op':str(uuid4())}
    state['cart']=[{'producto_id':1,'cantidad':1,'descuento':0}];shared.sync(repo)
    assert not repo.cart['items']


def test_freeze_cancel_and_success_refresh_the_shared_session(state):
    repo=Fake();state['cart']=[{'producto_id':1,'cantidad':1,'descuento':0}];shared.sync(repo);op=str(uuid4())
    shared.freeze(repo,op);assert state['shared_snapshot']['estado']=='COBRANDO'
    shared.finish(repo,op,cancel=True);shared.sync(repo);assert state['cart'][0]['cantidad']==1
    shared.freeze(repo,op);shared.finish(repo,op);state['cart']=[];shared.sync(repo);assert state['cart']==[]
