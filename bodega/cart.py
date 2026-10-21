"""Reglas del carrito de ventas, independientes de la interfaz."""
from decimal import Decimal, InvalidOperation
from bodega.repository import DataError


def product_row(products, product_id):
    if products.empty:
        raise DataError("No hay productos disponibles.")
    found = products.loc[products.id == int(product_id)]
    if found.empty:
        raise DataError("El producto ya no está disponible en el catálogo.")
    return found.iloc[0]


def _discount(value, subtotal):
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise DataError("Descuento inválido.") from None
    if not number.is_finite() or number < 0 or number > subtotal:
        raise DataError("El descuento debe estar entre cero y el subtotal del artículo.")
    return float(number.quantize(Decimal("0.01")))


def add_item(cart, products, product_id, quantity=1, discount=0):
    p = product_row(products, product_id)
    if not p.activo:
        raise DataError("Producto inactivo.")
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
        raise DataError("Cantidad inválida.")
    old = next((x for x in cart if x["producto_id"] == int(product_id)), None)
    qty = quantity + (old["cantidad"] if old else 0)
    if qty > int(p.stock):
        raise DataError("Stock insuficiente para agregar esa cantidad.")
    extra = _discount(discount, Decimal(str(p.precio)) * quantity)
    disc = Decimal(str(extra)) + Decimal(str(old["descuento"] if old else 0))
    value = _discount(disc, Decimal(str(p.precio)) * qty)
    if old:
        old.update(cantidad=qty, descuento=value)
    else:
        cart.append({"producto_id": int(product_id), "cantidad": qty, "descuento": value})
    return cart


def change_quantity(cart, products, product_id, quantity):
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 0:
        raise DataError("Cantidad inválida.")
    p = product_row(products, product_id)
    item = next((x for x in cart if x["producto_id"] == int(product_id)), None)
    if item is None:
        return cart
    if quantity <= 0:
        cart.remove(item)
        return cart
    if not p.activo or quantity > int(p.stock):
        raise DataError("Stock insuficiente para esa cantidad.")
    _discount(item["descuento"], Decimal(str(p.precio)) * quantity)
    item["cantidad"] = int(quantity)
    return cart


def set_discount(cart, products, product_id, discount):
    p = product_row(products, product_id)
    item = next(x for x in cart if x["producto_id"] == int(product_id))
    item["descuento"] = _discount(discount, Decimal(str(p.precio)) * item["cantidad"])


def lines(cart, products):
    result = []
    for item in cart:
        p = product_row(products, item["producto_id"])
        subtotal = Decimal(str(p.precio)) * item["cantidad"]
        disc = Decimal(str(item["descuento"]))
        result.append({"producto_id": int(p.id), "nombre": p.nombre, "codigo": p.codigo,
            "cantidad": item["cantidad"], "precio": float(p.precio), "descuento": float(disc),
            "subtotal": float(subtotal), "total": float(subtotal - disc),
            "stock": int(p.stock), "activo": bool(p.activo)})
    return result


def totals(cart_lines):
    subtotal = sum((Decimal(str(r["subtotal"])) for r in cart_lines), Decimal(0))
    discount = sum((Decimal(str(r["descuento"])) for r in cart_lines), Decimal(0))
    return {"subtotal": float(subtotal), "descuento": float(discount), "total": float(subtotal-discount)}
