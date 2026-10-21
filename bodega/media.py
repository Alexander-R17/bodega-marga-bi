"""URL de imágenes: solo texto en PostgreSQL; los bytes los sirve su origen."""
import json
from urllib.parse import urlsplit

MAX_IMAGES = 8


def valid_image_url(url):
    if not url:
        return True
    if not isinstance(url, str) or len(url) > 2048 or any(c.isspace() for c in url):
        return False
    try:
        p = urlsplit(url)
        return p.scheme == "https" and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False


def normalize_urls(values):
    if not isinstance(values, list) or len(values) > MAX_IMAGES:
        raise ValueError(f"Puedes guardar hasta {MAX_IMAGES} URL de imagen por producto.")
    result = []
    for i, value in enumerate(values, 1):
        if not isinstance(value, str):
            raise ValueError(f"La URL de imagen {i} no es válida.")
        value = value.strip()
        if value and not valid_image_url(value):
            raise ValueError(f"La imagen {i} debe usar una URL HTTPS válida, sin espacios ni credenciales.")
        if value and value not in result:
            result.append(value)
    return result


def product_urls(product):
    raw = product.get("imagenes_urls", [])
    if isinstance(raw, str):
        try: raw = json.loads(raw)
        except (ValueError, TypeError): raw = []
    values = raw if isinstance(raw, list) else []
    legacy = product.get("imagen_url", "")
    if not values and isinstance(legacy, str) and legacy.strip():
        values = [legacy.strip()]
    result = []
    for value in values:
        if isinstance(value, str) and value.strip() and valid_image_url(value.strip()) and value.strip() not in result:
            result.append(value.strip())
    return result[:MAX_IMAGES]
