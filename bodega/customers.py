"""Selección privada de clientes y entradas de DNI con validación en dos capas."""
import streamlit as st
from bodega.checkout import customer_data
from bodega.repository import DataError


def dni_input(label, *, key, container=st):
    # Texto para conservar ceros iniciales; tel ofrece teclado numérico en Android.
    return container.text_input(label, key=key, max_chars=8, type='phone', icon='',
        placeholder='8 dígitos', autocomplete='off',
        validate=(r'^[0-9]{8}$', 'El DNI debe contener exactamente 8 números, sin letras ni espacios.'))


def checkout_customer(repo):
    query=st.text_input('Buscar cliente registrado por nombre o DNI', max_chars=120,
                        key='sale_customer_search', autocomplete='off')
    clients=repo.search_customers(query)
    labels={c['id']:f"{c['nombre']} · DNI {c['dni']}" for c in clients}
    options=[None]+list(labels)
    if st.session_state.get('sale_registered_customer') not in options:
        st.session_state['sale_registered_customer']=None
    selected=st.selectbox('Cliente registrado', options,
        format_func=lambda x:labels.get(x,'Consumidor final o cliente nuevo'), key='sale_registered_customer')
    if selected is not None:
        client=next(c for c in clients if c['id']==selected)
        st.caption('El nombre y DNI se toman de la ficha del cliente.')
        return customer_data(client),True
    a,b=st.columns([1,2])
    dni=dni_input('DNI del cliente (opcional)',key='sale_customer_dni',container=a)
    name=b.text_input('Nombre del cliente (opcional)',max_chars=120,key='sale_customer_name',autocomplete='off')
    st.caption('Deja ambos vacíos para Consumidor final. Un cliente con DNI se guardará al registrar su venta.')
    try:return customer_data({'dni':dni,'nombre':name}),True
    except DataError as exc:
        st.error(str(exc));return {},False
