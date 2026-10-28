"""Búsqueda y autocompletado privado de los campos visibles de cliente."""
import streamlit as st
from bodega.checkout import customer_data
from bodega.repository import DataError

def dni_input(label, *, key, container=st):
    return container.text_input(label,key=key,max_chars=8,type='phone',placeholder='8 dígitos',autocomplete='off',live='300ms')

def changed(source):
    st.session_state['customer_change']=source;st.session_state['payment_received']=False;st.session_state['reset_payment_confirmation']=True

def fill(client):
    st.session_state['sale_customer_dni']=client['dni'];st.session_state['sale_customer_name']=client.get('nombre') or ''

def checkout_customer(repo):
    source=st.session_state.pop('customer_change',None)
    query=st.text_input('Buscar cliente por nombre o DNI',key='sale_customer_search',max_chars=120,live='400ms',on_change=changed,args=('search',))
    clients=repo.search_customers(query)
    if source=='search':
        st.session_state['sale_registered_customer']=None
        fill(next((c for c in clients if c['dni']==query),{'dni':query if len(query)==8 and query.isascii() and query.isdigit() else '','nombre':''}))
    if source=='dni':
        st.session_state['sale_registered_customer']=None;dni=st.session_state.get('sale_customer_dni','')
        found=next((c for c in repo.search_customers(dni) if c['dni']==dni),{}) if len(dni)==8 and dni.isascii() and dni.isdigit() else {}
        st.session_state['sale_customer_name']=found.get('nombre') or ''
    labels={c['id']:f"{c.get('nombre') or 'Cliente sin nombre'} · DNI {c['dni']}" for c in clients};options=[None]+list(labels)
    if st.session_state.get('sale_registered_customer') not in options:st.session_state['sale_registered_customer']=None
    selected=st.selectbox('Resultados de clientes',options,key='sale_registered_customer',format_func=lambda x:labels.get(x,'Selecciona un cliente o ingresa un DNI nuevo'),on_change=changed,args=('selection',))
    if source=='selection' and selected is not None:fill(next(c for c in clients if c['id']==selected))
    a,b=st.columns([1,2]);dni=a.text_input('DNI del cliente',key='sale_customer_dni',max_chars=8,type='phone',live='300ms',on_change=changed,args=('dni',))
    name=b.text_input('Nombre del cliente (opcional)',key='sale_customer_name',max_chars=120,on_change=changed,args=('name',))
    try:return customer_data({'dni':dni,'nombre':name}),True
    except DataError as exc:
        (st.error if dni or name else st.caption)(str(exc));return {},False
