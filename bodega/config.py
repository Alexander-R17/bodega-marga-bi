import os
import streamlit as st


def setting(name, default=""):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return os.getenv(name, default)


def mode():
    value = str(setting("APP_MODE", "demo")).lower()
    if value not in {"cloud", "demo"}:
        raise ValueError("APP_MODE debe ser cloud o demo.")
    return value
