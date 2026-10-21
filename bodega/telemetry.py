"""Medición interna por sesión de Streamlit, sin datos de clientes ni dispositivo."""
from uuid import uuid4
import streamlit as st
from bodega.repository import DataError
from bodega.auth import AccessError


def record(repo, event, detail="", page=None):
    session = st.session_state.setdefault("measurement_session", str(uuid4()))
    page = page or st.session_state.get("page", "Inicio")
    try:
        repo.event(event, detail, session_id=session, page=page)
        return True
    except (DataError, AccessError):
        return False
