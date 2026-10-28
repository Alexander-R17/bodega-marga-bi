"""Carrito compartido por UID; la base controla versión, reintentos y bloqueo de cobro."""
from copy import deepcopy
from uuid import uuid4
import streamlit as st
from bodega.auth import identity_scope
from bodega.config import mode
from bodega.repository import DataError


def available(repo):
    return mode()=='cloud' and hasattr(repo,'native_ready') and repo.native_ready()


def adopt(snapshot):
    st.session_state['shared_snapshot']=snapshot
    st.session_state['cart']=deepcopy(snapshot['items'])
    st.session_state['reset_payment_confirmation']=True


def sync(repo):
    if not available(repo):return
    if any(k in st.session_state for k in ('pending_sale','pending_credit','active_charge')):return
    previous=st.session_state.get('shared_snapshot')
    current=deepcopy(st.session_state.get('cart',[]))
    if previous and current!=previous['items']:
        candidate=st.session_state.setdefault('shared_upload',{'op':str(uuid4()),'items':current,'revision':previous['revision']})
        try:
            result=repo.shared_write(**candidate)
            st.session_state.pop('shared_upload',None);adopt(result)
        except DataError as exc:
            if 'otro dispositivo' not in str(exc):raise
            st.session_state.pop('shared_upload',None);adopt(repo.shared_read())
            st.session_state['shared_notice']='El carrito cambió en otro dispositivo. Se cargó la versión actual; revisa y repite tu último cambio.'
    elif not previous:
        result=repo.shared_read()
        if current and not result['items'] and result['estado']=='ABIERTO':
            result=repo.shared_write(str(uuid4()),current,result['revision'])
        elif current and result['items']!=current:
            st.session_state['previous_local_cart']=current
            st.session_state['shared_notice']='Se cargó el carrito compartido. Se conservó una copia del carrito local anterior en esta sesión.'
        adopt(result)


def freeze(repo,op):
    if not available(repo):return
    previous=st.session_state.get('shared_snapshot') or repo.shared_read()
    result=repo.shared_freeze(op,previous['revision'])
    if result.get('estado')!='TERMINADO':st.session_state['shared_snapshot']=result


def finish(repo,op,cancel=False):
    if not available(repo):return
    try:repo.shared_finish(op,cancel)
    except DataError:
        if cancel:raise
        # La venta ya está confirmada; la consulta del carrito recupera el cierre por su operación.
    st.session_state.pop('shared_snapshot',None)
    st.session_state.pop('shared_upload',None)


@st.fragment(run_every=3)
def monitor(repo):
    if not available(repo):return
    if any(k in st.session_state for k in ('pending_sale','pending_credit','active_charge','shared_upload')):return
    with identity_scope():
        result=repo.shared_read()
    previous=st.session_state.get('shared_snapshot')
    if previous is None:
        sync(repo);st.rerun(scope='app')
    if previous and (previous.get('revision')!=result['revision'] or previous.get('catalogo_revision')!=result.get('catalogo_revision')):
        # No publicar una copia vieja después de que otro dispositivo la cambie.
        if st.session_state.get('cart',[])==previous['items']:
            adopt(result);repo.clear_cache();st.rerun(scope='app')
    st.caption('Carrito e inventario compartidos · actualización cada 3 segundos')


def status(repo):
    notice=st.session_state.pop('shared_notice',None)
    if notice:st.warning(notice)
    snap=st.session_state.get('shared_snapshot',{})
    if snap.get('estado')!='COBRANDO' or any(k in st.session_state for k in ('pending_sale','pending_credit','active_charge')):return False
    op=snap.get('operacion')
    # Recuperación de una ventana Yape tras cerrar o recargar el navegador.
    try:
        result=repo.charge_status(op)
        if result.get('estado') not in {'CANCELADO','VENCIDO','REGISTRADO'}:
            st.session_state['active_charge']={'id':op};st.session_state['shop_view']='carrito';st.rerun()
    except DataError as exc:
        if not exc.confirmed_rejected:raise
    st.warning('Este carrito quedó bloqueado por una operación de cobro. Revisa el historial antes de liberarlo; no vuelvas a cobrar.')
    checked=st.checkbox('Revisé el historial y resolveré cualquier pago recibido sin pedir otro pago',key='shared_unlock_review')
    if st.button('Liberar carrito pendiente',disabled=not checked):
        try:
            # Si existe una orden Yape vencida/cancelada, el servidor permite liberar; una activa se conserva.
            finish(repo,op,cancel=True);st.rerun()
        except DataError as exc:st.error(str(exc))
    return True
