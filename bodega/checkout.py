"""Datos declarados de cliente y conciliación manual, sin consultas a RENIEC/bancos."""
import re
from bodega.repository import DataError


def customer_data(customer=None):
    customer=customer or {}
    if not isinstance(customer,dict):
        raise DataError("Datos del cliente inválidos.")
    dni=str(customer.get("dni","") or "").strip()
    name=" ".join(str(customer.get("nombre","") or "").split())
    if (dni and (not re.fullmatch(r"[0-9]{8}",dni) or not name)) or (name and not 2<=len(name)<=120):
        raise DataError("Datos del cliente inválidos: usa un DNI de 8 dígitos y su nombre, o deja ambos vacíos.")
    return {"dni":dni,"nombre":name}


def payment_data(payment,reference="",entity=""):
    if payment not in {"Efectivo","Yape","Plin","Tarjeta","Transferencia","Fiado"}:
        raise DataError("Medio de pago inválido.")
    if payment in {"Efectivo","Fiado"}: return {"reference":"","entity":""}
    reference=str(reference or "").strip().upper()
    entity=" ".join(str(entity or "").split()).upper()
    if not re.fullmatch(r"[A-Z0-9._/-]{4,100}",reference) or not entity or len(entity)>60:
        raise DataError("Referencia de pago requerida: ingresa el código de la operación y la entidad receptora.")
    return {"reference":reference,"entity":entity}


def order_number(vid):
    return f"VM-{int(vid):08d}"
