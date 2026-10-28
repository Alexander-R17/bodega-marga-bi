"""Cuentas por cobrar: ventas a crédito, abonos y reversos con trazabilidad."""
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo
import re
import streamlit as st
from bodega.config import setting,mode
from bodega.repository import DataError
from bodega.ui import page_header
from bodega.checkout import customer_data,payment_data
from bodega.payments import fingerprint,confirmed_amount


def enabled():
    return mode()=='demo' or setting('CREDIT_ENABLED',False) is True


def account_data(dni,name,limit):
    customer=customer_data({'dni':dni,'nombre':name})
    amount=confirmed_amount(limit)
    if not customer['dni'] or amount>1000000:
        raise DataError('Datos de cuenta de fiado inválidos')
    return customer,amount


def _complete_sale(repo,pending,finish,notify):
    try:
        result=repo.credit_sale(**pending)
    except DataError as exc:
        st.error(str(exc));return
    st.session_state['last_sale_receipt']={**result,'payment':'Fiado'}
    st.session_state.pop('pending_credit',None)
    st.session_state['cart']=[];st.session_state['reset_payment_confirmation']=True
    notify(repo,'venta_fiada_registrada')
    finish(f"Venta {result['orden']} registrada a fiado. El dinero queda pendiente de cobro.")


def pending_checkout(repo,finish,notify):
    pending=st.session_state.get('pending_credit')
    if not pending:return False
    st.warning(f"Venta a fiado pendiente de respuesta: S/ {float(pending['total']):.2f}. Conserva esta operación al reintentar.")
    if st.button('Reintentar venta a fiado',type='primary'):_complete_sale(repo,pending,finish,notify)
    st.caption('Si no hubo respuesta, revisa el historial antes de abandonar la operación. No generes otra venta para el mismo pedido.')
    if st.button('Dejar de reintentar y revisar el historial'):
        del st.session_state['pending_credit'];st.session_state['page']='Historial de ventas';st.rerun()
    return True


def choose_account(repo):
    query=st.text_input('Buscar cuenta de fiado por nombre o DNI',max_chars=120,key='sale_credit_search',autocomplete='off')
    accounts=repo.credit_overview(query=query)['cuentas']
    if not accounts:
        st.info('No hay cuentas de fiado con esa búsqueda. El administrador puede crearlas en Fiados.')
        return None
    labels={x['id']:f"{x['nombre']} · DNI {x['dni']}"+(' · Bloqueada' if not x['activo'] else '') for x in accounts}
    if st.session_state.get('sale_credit_account') not in labels:
        st.session_state['sale_credit_account']=None
    selected=st.selectbox('Cliente con cuenta de fiado',list(labels),index=None,
        placeholder='Selecciona al titular de la cuenta',format_func=labels.get,key='sale_credit_account')
    st.caption('Solo se utilizan cuentas creadas en Fiados. El nombre y DNI se completan desde su ficha.')
    return next((x for x in accounts if x['id']==selected),None)


def checkout(repo,rows,total,account,items,finish,notify):
    if not enabled():st.info('Activa CREDIT_ENABLED después de ejecutar SQL 08.');return
    if not account:st.info('Selecciona un cliente con cuenta de fiado para continuar.');return
    customer=customer_data({'dni':account['dni'],'nombre':account['nombre']})
    balance=Decimal(str(account['saldo']));available=Decimal(str(account['limite']))-balance
    st.write(f"**Cuenta: {account['nombre']}**")
    st.caption(f"Deuda actual: S/ {balance:.2f} · Disponible: S/ {max(available,Decimal(0)):.2f}")
    today=datetime.now(ZoneInfo('America/Lima')).date()
    due=st.date_input('Fecha de compromiso de pago',value=today+timedelta(days=7),min_value=today,max_value=today+timedelta(days=365),key='credit_due')
    signature=fingerprint(rows,'Fiado',customer=customer,reference=str(account['id']),entity=str(due))
    if st.session_state.get('credit_signature')!=signature:
        st.session_state['credit_signature']=signature;st.session_state['credit_authorized']=False
    valid=account['activo'] and Decimal(str(total))<=available
    if not account['activo']:st.warning('Esta cuenta está bloqueada para nuevas compras.')
    elif not valid:st.warning('El importe supera el crédito disponible.')
    authorized=st.checkbox('Autorizo entregar estos productos a fiado y registrar la deuda',key='credit_authorized',disabled=not valid)
    if st.button('Registrar venta a fiado',type='primary',disabled=not authorized or not valid,width='stretch'):
        pending={'op':str(uuid4()),'items':[dict(x) for x in items],'account':account['id'],'due':str(due),'total':str(total)}
        st.session_state['pending_credit']=pending;_complete_sale(repo,pending,finish,notify)
    st.caption('La venta descuenta inventario. El saldo solo disminuye cuando registras un abono. No se cobra interés.')


def render(repo,role,today):
    page_header('Cuentas de fiado','Consulta las deudas de tus clientes, registra abonos y revisa su historial.')
    if role not in {'administrador','cajero'}:st.info('Las cuentas identificadas corresponden a caja y administración.');return
    if not enabled():st.info('Ejecuta SQL 08 y activa CREDIT_ENABLED = true en los Secrets para habilitar este módulo.');return
    if role=='administrador':
        with st.expander('Habilitar cliente o cambiar su límite'):
            with st.form('credit_account_form',clear_on_submit=True):
                from bodega.customers import dni_input
                dni=dni_input('DNI de la cuenta',key='credit_account_dni');name=st.text_input('Nombre del titular',max_chars=120)
                limit=st.number_input('Límite total de fiado S/',min_value=0.,max_value=1000000.,value=100.,step=10.)
                active=st.checkbox('Habilitar nuevas compras',value=True)
                submit=st.form_submit_button('Guardar cuenta')
            if submit:
                try:
                    customer,limit=account_data(dni,name,limit);repo.configure_credit(customer['dni'],customer['nombre'],limit,active)
                    st.success('Cuenta actualizada. Un límite menor no elimina la deuda existente.')
                except DataError as exc:st.error(str(exc))
    query=st.text_input('Buscar cuenta por DNI o nombre',max_chars=120,key='credit_search')
    listing=repo.credit_overview(query=query)['cuentas']
    if not listing:st.info('No hay cuentas con esa búsqueda.');return
    st.caption('Hasta 100 cuentas por búsqueda. Los saldos se calculan con todo el historial de cada cuenta.')
    st.dataframe(listing,hide_index=True,width='stretch')
    labels={x['id']:x['dni']+' · '+x['nombre'] for x in listing}
    account_id=st.selectbox('Cuenta para consultar',list(labels),format_func=labels.get,key='credit_selected_account')
    account=next(x for x in listing if x['id']==account_id);data=repo.credit_overview(query=query,account=account_id)
    a,b,c=st.columns(3);a.metric('Deuda pendiente',f"S/ {float(account['saldo']):.2f}")
    b.metric('Límite autorizado',f"S/ {float(account['limite']):.2f}")
    c.metric('Disponible',f"S/ {max(0,float(account['limite'])-float(account['saldo'])):.2f}")
    st.subheader('Ventas a fiado y vencimientos');st.dataframe(data['cargos'],hide_index=True,width='stretch')
    st.caption('Detalle: hasta 250 cargos y 250 abonos recientes. Los abonos no generan otra venta ni otro movimiento de stock.')
    pending=st.session_state.get('pending_credit_payment')
    if pending:
        st.warning(f"Abono pendiente de respuesta: venta {pending['sale']} · S/ {float(pending['amount']):.2f}")
        if st.button('Reintentar el mismo abono'):
            try:
                repo.credit_payment(**pending);del st.session_state['pending_credit_payment'];st.rerun()
            except DataError as exc:st.error(str(exc))
        if st.button('Revisar historial y dejar de reintentar'):
            del st.session_state['pending_credit_payment'];st.rerun()
    else:
        debts={r['venta_id']:r for r in data['cargos'] if r['estado']=='COMPLETADA' and Decimal(str(r['saldo']))>0}
        if debts:
            with st.form('credit_payment_form',clear_on_submit=True):
                st.subheader('Registrar abono recibido')
                sale=st.selectbox('Venta que se está pagando',list(debts),format_func=lambda k:debts[k]['orden']+f" · saldo S/ {float(debts[k]['saldo']):.2f}")
                amount=st.number_input('Importe del abono S/',min_value=0.01,max_value=1000000.,value=1.,step=1.)
                payment=st.selectbox('Medio del abono',['Efectivo','Yape','Plin','Transferencia','Tarjeta'])
                reference=st.text_input('Referencia del abono (vacía si es efectivo)',max_chars=100)
                entity=st.text_input('Entidad receptora del abono (vacía si es efectivo)',max_chars=60)
                checked=st.checkbox('Comprobé que recibí este abono en efectivo o en la cuenta del negocio')
                submit=st.form_submit_button('Guardar abono',type='primary')
            if submit:
                try:
                    if not checked:raise DataError('Confirma el abono recibido antes de registrarlo.')
                    details=payment_data(payment,reference,entity);value=confirmed_amount(amount)
                    if value>Decimal(str(debts[sale]['saldo'])):raise DataError('El abono supera la deuda pendiente')
                    pending={'op':str(uuid4()),'sale':sale,'amount':str(value),'payment':payment,
                             'reference':details['reference'],'entity':details['entity']}
                    st.session_state['pending_credit_payment']=pending
                    repo.credit_payment(**pending);del st.session_state['pending_credit_payment'];st.rerun()
                except DataError as exc:st.error(str(exc))
    st.subheader('Historial de abonos');st.dataframe(data['abonos'],hide_index=True,width='stretch')
    if role=='administrador':
        reversible={a['id']:a for a in data['abonos'] if not a.get('anulado_en')}
        if reversible:
            with st.expander('Anular un abono registrado por error'):
                selected=st.selectbox('Abono para anular',list(reversible),format_func=lambda k:f"{k[:8]} · S/ {float(reversible[k]['importe']):.2f}")
                reason=st.text_input('Motivo de anulación del abono',max_chars=160)
                checked=st.checkbox('Revisé el abono y concilié cualquier devolución por separado')
                if st.button('Anular abono',disabled=not checked or len(reason.strip())<3):
                    repo.reverse_credit_payment(selected,reason);st.rerun()
