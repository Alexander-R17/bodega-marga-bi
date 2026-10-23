"""Historial paginado por servidor; acceso a clientes solo para caja y administración."""
from datetime import timedelta
import pandas as pd
import streamlit as st
from bodega.ui import page_header
from bodega.analytics import csv_export
from bodega.receipts import receipt_panel


def _page(delta):
    st.session_state['history_page']=max(0,st.session_state.get('history_page',0)+delta)
    st.session_state.pop('history_ticket_id',None)


def render(repo,role,today):
    page_header('Historial de ventas','Busca por DNI, nombre, número de orden o ticket de importación y vuelve a descargar el ticket.')
    if role not in {'administrador','cajero'}:
        st.info('El historial identificado de clientes corresponde a caja y administración.'); return
    initial={'since':today-timedelta(days=29),'until':today,'query':'','status':'TODOS','payment':'Todos'}
    filters=st.session_state.setdefault('history_filters',initial)
    with st.form('history_filters_form'):
        a,b,c=st.columns([1,1,2])
        since=a.date_input('Desde',value=filters['since'],key='history_since')
        until=b.date_input('Hasta',value=filters['until'],key='history_until')
        query=c.text_input('DNI, cliente, orden o ticket',value=filters['query'],max_chars=120,key='history_search')
        a,b=st.columns(2)
        status=a.selectbox('Estado',['TODOS','COMPLETADA','ANULADA'],key='history_status')
        payment=b.selectbox('Medio de pago',['Todos','Efectivo','Yape','Plin','Tarjeta','Transferencia'],key='history_payment')
        search=st.form_submit_button('Buscar ventas',type='primary')
    if search:
        if since>until: st.error('La fecha inicial debe ser anterior o igual a la final.'); return
        filters={'since':since,'until':until,'query':query.strip(),'status':status,'payment':payment}
        st.session_state['history_filters']=filters
        st.session_state['history_page']=0
        st.session_state.pop('history_ticket_id',None)
    page=st.session_state.get('history_page',0)
    result=repo.search_sales(**filters,page=page,size=25)
    data=pd.DataFrame(result['rows']);total=int(result['total']);pages=max(1,(total+24)//25)
    if page>=pages:
        st.session_state['history_page']=0;st.rerun()
    st.caption(f'{total} ventas encontradas. Página {page+1} de {pages}. Fechas de operación en Lima.')
    if data.empty: st.info('No hay ventas con los filtros aplicados.'); return
    visible=data[['orden','fecha','cliente_nombre','cliente_dni','medio_pago','total','estado','pago_referencia']].rename(
        columns={'orden':'Orden','fecha':'Fecha','cliente_nombre':'Cliente','cliente_dni':'DNI','medio_pago':'Pago',
                 'total':'Total S/','estado':'Estado','pago_referencia':'Operación de pago'})
    st.dataframe(visible,hide_index=True,width='stretch')
    st.download_button('Exportar esta página CSV',csv_export(visible),'ventas_pagina.csv','text/csv',on_click='ignore')
    prev,position,nxt=st.columns([1,3,1])
    prev.button('Anterior',disabled=page==0,on_click=_page,args=(-1,))
    nxt.button('Siguiente',disabled=page+1>=pages,on_click=_page,args=(1,))
    labels=dict(zip(data.id,data.orden))
    vid=st.selectbox('Venta para consultar el ticket',data.id.tolist(),format_func=labels.get,key='history_selected_sale')
    if st.button('Ver ticket / reimprimir'):
        st.session_state['history_ticket_id']=int(vid)
    if 'history_ticket_id' in st.session_state:
        receipt_panel(repo,st.session_state['history_ticket_id'])
    st.caption('Las ventas anteriores conservan su información original. No asignamos nombres ni DNI a los registros históricos de demostración.')
