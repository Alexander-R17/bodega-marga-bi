import csv
import hashlib
import io
from decimal import Decimal, InvalidOperation
from datetime import datetime
from zoneinfo import ZoneInfo

COLUMNS = ["ticket", "fecha", "codigo", "cantidad", "precio_unitario", "costo_unitario", "descuento", "medio_pago"]
PAYMENTS = {"Efectivo", "Yape", "Plin", "Tarjeta", "Transferencia"}


def money(value):
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Número no válido") from None
    if not d.is_finite() or d < 0 or d != d.quantize(Decimal("0.01")):
        raise ValueError("Importe debe ser no negativo, con máximo dos decimales")
    return d


def validate_csv(raw, known_codes):
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("Máximo 5 MB por archivo")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("Guarda el CSV como UTF-8") from None
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != COLUMNS:
        raise ValueError("Encabezado incorrecto. Usa la plantilla y conserva el orden de columnas.")
    records, errors, seen, tickets = [], [], set(), {}
    for index, row in enumerate(reader, 2):
        if index > 2001:
            raise ValueError("Máximo 2000 filas por lote; divide archivos mayores.")
        try:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Número de columnas incorrecto")
            ticket = row["ticket"].strip()
            code = row["codigo"].strip()
            if not ticket or len(ticket) > 100:
                raise ValueError("Ticket vacío o muy largo")
            if code not in known_codes:
                raise ValueError("Código desconocido: " + code)
            fecha = datetime.strptime(row["fecha"].strip(), "%Y-%m-%d").date().isoformat()
            if fecha > datetime.now(ZoneInfo("America/Lima")).date().isoformat():
                raise ValueError("Fecha futura no permitida")
            qty = int(row["cantidad"])
            if str(qty) != row["cantidad"].strip() or not 1 <= qty <= 100000:
                raise ValueError("Cantidad debe ser un entero positivo")
            price, cost, discount = [money(row[c]) for c in COLUMNS[4:7]]
            if discount > qty * price:
                raise ValueError("Descuento mayor que subtotal")
            payment = row["medio_pago"].strip()
            if payment not in PAYMENTS:
                raise ValueError("Medio de pago desconocido")
            if (ticket, code) in seen:
                raise ValueError("Ticket y producto repetidos; consolida la cantidad")
            if ticket in tickets and tickets[ticket] != (fecha, payment):
                raise ValueError("Fecha o pago inconsistentes dentro de un ticket")
            seen.add((ticket, code))
            tickets[ticket] = (fecha, payment)
            records.append({"ticket": ticket, "fecha": fecha, "codigo": code, "cantidad": qty,
                "precio_unitario": str(price), "costo_unitario": str(cost), "descuento": str(discount),
                "medio_pago": payment})
        except (ValueError, TypeError) as exc:
            errors.append({"fila": index, "error": str(exc)})
    if not records and not errors:
        raise ValueError("CSV vacío")
    return records, errors, hashlib.sha256(raw).hexdigest()
