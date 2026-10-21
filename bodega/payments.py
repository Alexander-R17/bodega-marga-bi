"""Confirmación manual de caja, vinculada a artículos, precios y medio de pago."""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from bodega.repository import DataError


def fingerprint(lines, payment):
    payload = {"payment": payment, "lines": [
        {key: line[key] for key in ("producto_id", "cantidad", "precio", "descuento")}
        for line in sorted(lines, key=lambda item: item["producto_id"])]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def confirmed_amount(value):
    if value is None or isinstance(value, bool):
        raise DataError("Confirma que recibiste el pago completo antes de registrar la venta.")
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
            raise ValueError
    except (InvalidOperation, ValueError):
        raise DataError("El importe del pago confirmado no es válido.") from None
    return amount
