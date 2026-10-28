"""Espera de Yape por orden; registro atómico basado en el aviso del receptor."""
import hashlib
import json
import secrets
import time
from uuid import uuid4
import streamlit as st
from bodega.auth import identity_scope
from bodega.config import setting
from datetime import datetime, timezone
from bodega.repository import DataError


def enabled():
    return setting('PAYMENT_NOTIFICATIONS_ENABLED',False) is True


def _done(result):
    st.session_state['last_sale_receipt']={**result,'payment':'Yape'}
    st.session_state['cart']=[];st.session_state['reset_payment_confirmation']=True
    st.session_state.pop('active_charge',None)
    st.session_state['show_yape_success']=True
    st.session_state['flash']='Venta registrada a partir del aviso de Yape del celular vinculado.'
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
                st.button('Reintentar consulta',key='charge_transport_retry')
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
            with st.status('Aviso recibido. Comprobando y registrando la venta…',state='running',expanded=True):
                st.write('Estamos asociando el aviso a esta orden y comprobando que no esté repetido.')
                try:
                    with identity_scope():result=repo.confirm_charge_notice(op)
                    if result.get('estado')=='REGISTRADO':_done(result)
                    else:st.caption('Comprobando avisos del mismo importe. Espera unos segundos.')
                except DataError as exc:
                    st.error(str(exc))
                    st.caption('La venta no se mostrará como exitosa hasta recibir la confirmación del servidor. No solicites otro pago.')
        elif state=='AMBIGUO':
            st.warning('Hay varios avisos del mismo importe. No se puede asignar uno automáticamente.')
            st.write('No se registrará automáticamente. Revisa los movimientos en el Yape del negocio y concilia el cobro antes de entregar los productos.')
        elif state in {'VENCIDO','CANCELADO'}:
            st.warning('La espera terminó. No se registró una venta con esta orden.')
            if status.get('aviso_id'):
                st.info('El aviso recibido sigue guardado. Entra como administrador en Actividad → Cobros recibidos pendientes de registro para revisar y recuperar esta venta.')
            st.caption('Si el cliente ya pagó, revisa el abono y concilia el cobro con el administrador. No solicites un segundo pago.')
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


def receiver_ready(device):
    try:
        stamp=datetime.fromisoformat(str(device.get('ultimo_contacto','')).replace('Z','+00:00'))
        age=(datetime.now(timezone.utc)-stamp).total_seconds()
        return device['activo'] and -5<=age<=1200
    except (ValueError,TypeError):return False


def checkout(repo,items,customer,total,valid):
    if not enabled() or not hasattr(repo,'receivers'):
        st.info('Yape requiere activar el lector del celular antes de cobrar. El administrador debe habilitar PAYMENT_NOTIFICATIONS_ENABLED y vincular el receptor.')
        st.button('Confirmar venta',type='primary',disabled=True,width='stretch',key='charge_start')
        return
    cache=st.session_state.get('charge_devices')
    if st.button('Actualizar conexión del celular',key='charge_devices_refresh'):
        cache=None;st.session_state.pop('charge_devices',None)
    if not cache or time.monotonic()-cache[0]>30:
        try:
            cache=(time.monotonic(),repo.receivers());st.session_state['charge_devices']=cache
        except DataError as exc:st.error(str(exc));return
    devices={d['id']:d for d in cache[1] if d['activo']}
    device=None
    if len(devices)>1:
        if st.session_state.get('charge_device') not in devices:st.session_state.pop('charge_device',None)
        device=st.selectbox('Celular receptor',list(devices),format_func=lambda k:devices[k]['nombre'],key='charge_device')
    elif devices:
        device=next(iter(devices));st.caption('Receptor: '+devices[device]['nombre'])
    ready=bool(device and receiver_ready(devices[device]))
    if not ready:
        st.warning('Falta conectar el celular receptor. Instala la app, importa el vínculo y pulsa Comprobar conexión en el teléfono. Después actualiza esta conexión.')
    else:st.caption('Al confirmar se abrirá la ventana de espera. Pide el Yape después de abrirla.')
    if st.button('Confirmar venta',type='primary',disabled=not valid or not ready,width='stretch',key='charge_start'):
        candidate=st.session_state.setdefault('charge_start_candidate',str(uuid4()))
        try:
            result=repo.start_charge(candidate,device,[dict(x) for x in items],customer,total)
            st.session_state['active_charge']={'id':result['id']};st.session_state.pop('charge_start_candidate',None)
            st.rerun()
        except DataError as exc:
            st.error(str(exc))
            if exc.confirmed_rejected:st.session_state.pop('charge_start_candidate',None)
    st.caption('Registro basado en el aviso del celular vinculado. No consulta el saldo del banco.')


def success_animation():
    st.markdown("""<style>
    @keyframes bodega-check {from{transform:scale(.4);opacity:0}to{transform:scale(1);opacity:1}}
    .bodega-payment-success{text-align:center;padding:24px;border:1px solid #b9dbcb;background:#f0faf4;border-radius:14px;color:#173b32}
    .bodega-payment-success span{display:inline-block;font-size:44px;animation:bodega-check .5s ease-out}
    @media(prefers-reduced-motion:reduce){.bodega-payment-success span{animation:none}}
    </style><div class="bodega-payment-success" role="status"><span>✓</span>
    <h3>Cobro registrado con éxito</h3><p>Aviso de Yape recibido · Venta guardada</p></div>""",unsafe_allow_html=True)


def admin(repo):
    if not enabled() or not hasattr(repo,'pair_receiver'):return
    reconciliation_admin(repo)
    with st.expander('Vincular celular receptor para Yape'):
        st.caption('Requiere SQL 07/09/10, la Edge Function recibir-aviso-yape y el APK del piloto Android.')
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


def reconciliation_admin(repo):
    if not hasattr(repo,'pending_received_charges'):return
    with st.expander('Cobros recibidos pendientes de registro'):
        st.caption('Para órdenes propias con un aviso ya asociado. Revisa el movimiento del Yape receptor antes de recuperar una venta; no solicites otro pago.')
        if st.button('Consultar cobros pendientes',key='received_charges_refresh'):
            st.session_state['received_charge_list']=repo.pending_received_charges()
        pending=st.session_state.get('received_charge_list',[])
        if not pending:
            st.info('Pulsa Consultar cobros pendientes. Solo aparecen órdenes con un aviso guardado y sin venta registrada.')
            return
        choices={c['id']:c for c in pending}
        if st.session_state.get('received_charge_selected') not in choices:
            st.session_state.pop('received_charge_selected',None)
        selected=st.selectbox('Orden recibida para recuperar',list(choices),key='received_charge_selected',
            format_func=lambda k:'CO-'+k[:8].upper()+f" · S/ {choices[k]['importe_centimos']/100:.2f} · "+choices[k]['cliente'])
        charge=choices[selected]
        st.write(f"**Cliente:** {charge['cliente']}")
        st.caption('Orden creada: '+str(charge['creado_en'])+' · Estado: '+charge['estado'])
        reviewed=st.checkbox('Comprobé el movimiento en Yape y corresponde al importe y al cliente de esta orden',
            key='received_charge_review_'+selected)
        if st.button('Recuperar venta con el aviso recibido',type='primary',disabled=not reviewed,key='received_charge_commit'):
            try:result=repo.reconcile_received_charge(selected,reviewed=True)
            except DataError as exc:
                st.error(str(exc));st.caption('La orden y el aviso se conservan. Reintenta esta misma recuperación después de revisar el error, sin cobrar de nuevo.')
                return
            st.session_state['last_sale_receipt']={**result,'payment':'Yape'}
            # Limpiar únicamente el carrito de la operación recuperada.
            same_order=st.session_state.get('active_charge',{}).get('id')==selected
            if same_order:
                st.session_state.pop('active_charge',None);st.session_state['cart']=[]
                st.session_state['reset_payment_confirmation']=True
            st.session_state.pop('received_charge_list',None)
            st.success('Venta '+result['orden']+' recuperada. Se utilizó el aviso existente; no se recibió ni solicitó otro pago.')
            if not same_order and st.session_state.get('cart'):
                st.info('Revisa el carrito antes de continuar. Si aún contiene los productos de esta venta recuperada, vacíalo para evitar registrarla otra vez.')
            from bodega.receipts import receipt_panel
            receipt_panel(repo,result['venta_id'])


def diagnostics(repo):
    if not hasattr(repo,'diagnose_checkout'):return
    with st.expander('Comprobar conexión y permisos de caja'):
        st.caption('Consulta de diagnóstico sin registrar ventas ni mostrar claves.')
        if st.button('Comprobar Supabase'):
            try:
                result=repo.diagnose_checkout()
                if result.get('ok'):st.success('Conexión de servidor y permisos de caja correctos.')
                else:st.warning('Faltan permisos en uno o más objetos. Ejecuta SQL 10 y vuelve a comprobar.')
                st.json(result)
            except DataError as exc:st.error(str(exc))
