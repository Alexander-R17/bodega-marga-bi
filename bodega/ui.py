"""Presentación visual del sistema. No modifica reglas de datos ni autenticación."""
from pathlib import Path
from base64 import b64encode
import html
import streamlit as st
from bodega.media import valid_image_url, product_urls

ROOT = Path(__file__).resolve().parents[1]
META_FIELDS = ["descripcion", "marca", "presentacion", "imagen_url"]


def inject_css():
    css = (ROOT / "assets" / "storefront.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def svg_uri(path):
    return "data:image/svg+xml;base64," + b64encode(Path(path).read_bytes()).decode()


def image_source(product):
    urls = product_urls(product)
    if urls:
        return urls[0]
    code = str(product.get("codigo", ""))
    file = ROOT / "assets" / "productos" / (code + ".svg") if code.isdigit() else None
    if file is None or not file.is_file():
        file = ROOT / "assets" / "productos" / "producto.svg"
    return svg_uri(file)


def product_image(product, css_class="product-image", selected_index=0):
    sources = product_urls(product) or [image_source(product)]
    index = int(selected_index) % len(sources)
    sources = sources[index:] + sources[:index]
    alt = html.escape(str(product.get("nombre", "Producto")), quote=True)
    first = f'<img class="gallery-base" src="{html.escape(sources[0], quote=True)}" alt="{alt}" loading="lazy">'
    frames = ""
    if len(sources) > 1:
        frames = ''.join(f'<img class="gallery-frame" src="{html.escape(src, quote=True)}" alt="" aria-hidden="true" '
            f'style="animation-delay:{i * 1.6}s" loading="lazy">' for i, src in enumerate(sources))
        frames += f'<span class="gallery-count">{len(sources)} fotos</span>'
    st.markdown(f'<div class="{css_class} product-gallery gallery-n{len(sources)}" style="--gallery-duration:{len(sources)*1.6}s">{first}{frames}</div>', unsafe_allow_html=True)


def page_header(title, text):
    st.markdown(f'<section class="page-heading"><span class="eyebrow">BODEGA MARGA / SISTEMA INTERNO</span><h1>{html.escape(title)}</h1><p>{html.escape(text)}</p></section>', unsafe_allow_html=True)


def status_badge(stock, minimum):
    label, color = ("Agotado", "empty") if stock == 0 else (("Stock bajo", "low") if stock <= minimum else ("Disponible", "ok"))
    return f'<span class="stock-badge {color}">{label}</span>'


def footer():
    st.markdown('<footer class="app-footer"><strong>BODEGA MARGA</strong><span>Sistema interno de ventas, inventario e inteligencia de negocios</span><span>Los Olivos, Lima · PEN</span></footer>', unsafe_allow_html=True)
