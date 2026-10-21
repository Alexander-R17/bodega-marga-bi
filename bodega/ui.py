"""Presentación visual del sistema. No modifica reglas de datos ni autenticación."""
from pathlib import Path
from base64 import b64encode
from urllib.parse import urlsplit
import html
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
META_FIELDS = ["descripcion", "marca", "presentacion", "imagen_url"]


def inject_css():
    css = (ROOT / "assets" / "storefront.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def svg_uri(path):
    return "data:image/svg+xml;base64," + b64encode(Path(path).read_bytes()).decode()


def image_source(product):
    url = str(product.get("imagen_url", "") or "").strip()
    if url and valid_image_url(url):
        return url
    code = str(product.get("codigo", ""))
    file = ROOT / "assets" / "productos" / (code + ".svg") if code.isdigit() else None
    if file is None or not file.is_file():
        file = ROOT / "assets" / "productos" / "producto.svg"
    return svg_uri(file)


def valid_image_url(url):
    if not url:
        return True
    try:
        parsed = urlsplit(url)
        return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def product_image(product, css_class="product-image"):
    source = image_source(product)
    if not source:
        source = svg_uri(ROOT / "assets" / "productos" / "producto.svg")
    st.markdown(f'<div class="{css_class}"><img src="{html.escape(source, quote=True)}" alt="{html.escape(str(product.get("nombre", "Producto")), quote=True)}" loading="lazy"></div>', unsafe_allow_html=True)


def page_header(title, text):
    st.markdown(f'<section class="page-heading"><span class="eyebrow">BODEGA MARGA / SISTEMA INTERNO</span><h1>{html.escape(title)}</h1><p>{html.escape(text)}</p></section>', unsafe_allow_html=True)


def status_badge(stock, minimum):
    label, color = ("Agotado", "empty") if stock == 0 else (("Stock bajo", "low") if stock <= minimum else ("Disponible", "ok"))
    return f'<span class="stock-badge {color}">{label}</span>'


def footer():
    st.markdown('<footer class="app-footer"><strong>BODEGA MARGA</strong><span>Sistema interno de ventas, inventario e inteligencia de negocios</span><span>Los Olivos, Lima · PEN</span></footer>', unsafe_allow_html=True)
