"""Espera por orden y receptor. Un aviso detectado requiere revisión en caja."""
import hashlib
import json
import secrets
import time
from uuid import uuid4
import streamlit as st
from bodega.auth import identity_scope
from bodega.config import setting
from bodega.checkout import payment_data
from bodega.repository import DataError


def enabled():
    return setting('PAYMENT_NOTIFICATIONS_ENABLED',False) is True


def _done(result):
    st.session_state['last_sale_receipt']={**result,'payment':'Yape'}
    st.session_state['cart']=[];st.session_state['reset_payment_confirmation']=True
    st.session_state.pop('active_charge',None)
    st.session_state['flash']='Venta registrada después de revisar el aviso y comprobar el abono en caja.'
    st.rerun(scope='app')


@st.dialog('Cobro por Yape',dismissible=False,width='small')
def _dialog(repo):
    @st.fragment(run_every=3)
    def monitor():
        op=st.session_state['active_charge']['id']
        with identity_scope():
            try:status=repo.charge_status(op)
            except DataError as exc:
                st.warning(str(exc));st.caption('La conexión puede estar interrumpida. Conserva esta orden y revisa el teléfono; no vuelvas a cobrar al cliente.')
                if st.button('Volver al carrito para revisar',key='charge_transport_close'):
                    # La orden sigue pendiente en el servidor hasta su vencimiento.
                    del st.session_state['active_charge'];st.rerun(scope='app')
                return
        state=status['estado'];st.markdown(f"### S/ {status['importe_centimos']/100:.2f}")
        st.caption('Orden de cobro CO-'+op[:8].upper()+' · consulta cada 3 segundos')
        if state=='REGISTRADO':
            from bodega.checkout import order_number
            _done({'venta_id':status['venta_id'],'total':status['importe_centimos']/100,'orden':order_number(status['venta_id'])})
        elif state=='ESPERANDO':
            with st.status('Esperando un aviso del celular receptor…',state='running',expanded=True):
                st.write('Pide al cliente que pague al Yape del negocio. Mantén conectado el celular receptor.')
                seconds=int(status.get('segundos_restantes',0));st.progress(max(0.,min(1.,1-seconds/120)))
                st.caption(f'Tiempo restante: {seconds} segundos. Todavía no se ha registrado una venta.')
        elif state=='DETECTADO':
            st.success('Pago detectado: llegó un aviso con el importe de esta orden.')
            st.caption('Comprueba el movimiento en el Yape receptor para identificar al comprador.')
            reference=st.text_input('Código de operación del abono',max_chars=100,key='charge_reference_'+op)
            checked=st.checkbox('Revisé el movimiento y recibí el importe completo de este cliente',key='charge_review_'+op)
            if st.button('Confirmar abono y registrar venta',type='primary',disabled=not checked,key='charge_commit_'+op):
                try:
                    details=payment_data('Yape',reference,'YAPE DEL NEGOCIO')
                    with identity_scope():result=repo.finish_charge(op,reference=details['reference'],entity=details['entity'],reviewed=True)
                    _done(result)
                except DataError as exc:st.error(str(exc))
        elif state=='AMBIGUO':
            st.warning('Hay varios avisos del mismo importe. No se puede asignar uno automáticamente.')
            st.write('Revisa los movimientos del receptor. Cancela la espera y utiliza la confirmación manual del carrito con la referencia correcta.')
        elif state in {'VENCIDO','CANCELADO'}:
            st.warning('La espera terminó. No se registró una venta con esta orden.')
            st.caption('Si el cliente ya pagó, revisa el abono y registra la venta manualmente. No solicites un segundo pago.')
        if state!='REGISTRADO' and st.button('Cerrar y volver al carrito',key='charge_cancel_'+op):
            try:
                with identity_scope():repo.finish_charge(op,cancel=True)
                st.session_state.pop('active_charge',None);st.rerun(scope='app')
            except DataError as exc:st.error(str(exc))
    monitor()


def active(repo):
    if 'active_charge' not in st.session_state:return False
    _dialog(repo)
    st.info('Hay una ventana de cobro abierta. Resuelve esa orden para continuar con el carrito.')
    return True


def checkout(repo,items,customer,total,valid):
    if not enabled() or not hasattr(repo,'receivers'):return
    with st.expander('Esperar aviso de Yape en una ventana'):
        st.caption('El lector debe estar instalado y activo en el teléfono receptor. Importe y hora orientan la asociación; el aviso no certifica el saldo del banco.')
        cache=st.session_state.get('charge_devices')
        if not cache or time.monotonic()-cache[0]>30:
            try:
                cache=(time.monotonic(),repo.receivers());st.session_state['charge_devices']=cache
            except DataError as exc:st.error(str(exc));return
        devices={d['id']:d['nombre'] for d in cache[1] if d['activo']}
        if not devices:st.info('El administrador debe vincular primero un celular en Actividad.');return
        device=st.selectbox('Celular receptor',list(devices),format_func=devices.get,key='charge_device')
        if st.button('Esperar el pago del cliente',type='secondary',disabled=not valid,key='charge_start'):
            candidate=st.session_state.setdefault('charge_start_candidate',str(uuid4()))
            try:
                result=repo.start_charge(candidate,device,[dict(x) for x in items],customer,total)
                st.session_state['active_charge']={'id':result['id']};st.session_state.pop('charge_start_candidate',None)
                st.rerun()
            except DataError as exc:
                st.error(str(exc))
                if exc.confirmed_rejected:st.session_state.pop('charge_start_candidate',None)


def admin(repo):
    if not enabled() or not hasattr(repo,'pair_receiver'):return
    with st.expander('Vincular celular receptor para Yape'):
        st.caption('Requiere SQL 07/09, la Edge Function recibir-aviso-yape y el APK del piloto Android.')
        name=st.text_input('Nombre del celular',value='S23 Ultra · caja',max_chars=60)
        if st.button('Crear vínculo privado del celular'):
            token=secrets.token_hex(32);device=str(uuid4())
            repo.pair_receiver(device,name,hashlib.sha256(token.encode()).hexdigest())
            st.session_state['charge_pairing']={'endpoint':repo.url+'/functions/v1/recibir-aviso-yape','device_id':device,'token':token}
            st.session_state.pop('charge_devices',None)
        if st.session_state.get('charge_pairing'):
            st.download_button('Descargar vínculo para importar en Android',json.dumps(st.session_state['charge_pairing'],indent=2),
                file_name='vinculo_receptor_PRIVADO.json',mime='application/json')
            st.caption('Mantén este archivo privado y elimínalo después de importarlo. Nunca lo subas a GitHub.')
            if st.button('Olvidar el vínculo descargable de esta sesión'):
                del st.session_state['charge_pairing'];st.rerun()
        if st.button('Consultar celulares vinculados'):
            st.session_state['charge_admin_devices']=repo.receivers()
        devices=st.session_state.get('charge_admin_devices',[])
        if devices:
            st.dataframe(devices,hide_index=True,width='stretch')
            active={d['id']:d['nombre']+' · '+d['id'][:8] for d in devices if d['activo']}
            if active:
                selected=st.selectbox('Receptor para desvincular',list(active),format_func=active.get)
                if st.button('Revocar vínculo del receptor'):
                    repo.revoke_receiver(selected);st.session_state.pop('charge_admin_devices',None)
                    st.session_state.pop('charge_devices',None);st.success('Vínculo revocado.')
