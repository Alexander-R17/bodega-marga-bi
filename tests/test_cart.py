import pandas as pd
import pytest
from bodega import cart
from bodega.repository import DataError
from bodega.storefront import filter_catalog


@pytest.fixture
def products():
    return pd.DataFrame([
        dict(id=1,nombre="Arroz",codigo="001",precio=4.8,stock=3,activo=True,categoria="Abarrotes"),
        dict(id=2,nombre="Leche",codigo="002",precio=4.2,stock=0,activo=True,categoria="Lácteos"),
        dict(id=3,nombre="Agua",codigo="003",precio=2.0,stock=10,activo=False,categoria="Bebidas")])


def test_aggregate_stock_and_total_with_discount(products):
    items=[]
    cart.add_item(items,products,1,2,.5)
    cart.add_item(items,products,1,1,.2)
    assert len(items)==1 and items[0]["cantidad"]==3
    assert cart.totals(cart.lines(items,products))==dict(subtotal=14.4,descuento=.7,total=13.7)
    with pytest.raises(DataError):cart.add_item(items,products,1)
    assert items[0]["cantidad"]==3


def test_quantity_discount_and_remove(products):
    items=[];cart.add_item(items,products,1,2)
    cart.set_discount(items,products,1,5)
    with pytest.raises(DataError):cart.change_quantity(items,products,1,1)
    assert items[0]["cantidad"]==2
    cart.set_discount(items,products,1,0)
    cart.change_quantity(items,products,1,1)
    cart.change_quantity(items,products,1,0)
    assert not items


@pytest.mark.parametrize("pid,qty,discount",[(2,1,0),(3,1,0),(1,0,0),(1,1.5,0),(1,True,0),(1,1,5),(1,1,-1),(1,1,"NaN"),(1,1,"abc")])
def test_invalid_cart_never_changes_items(products,pid,qty,discount):
    items=[]
    with pytest.raises(DataError):cart.add_item(items,products,pid,qty,discount)
    assert not items


def test_catalog_search_category_stock_price_and_sort(products):
    assert list(filter_catalog(products,query="001").id)==[1]
    assert list(filter_catalog(products,query="leCHe").id)==[2]
    assert list(filter_catalog(products,category="Lácteos").id)==[2]
    assert list(filter_catalog(products,in_stock=True).id)==[1]
    assert list(filter_catalog(products,price_range=(0,4.5)).id)==[2]
    assert list(filter_catalog(products,sort="Precio de menor a mayor").id)==[2,1]
    sales=pd.DataFrame([dict(producto_id=2,cantidad=10),dict(producto_id=1,cantidad=2)])
    assert list(filter_catalog(products,sort="Más vendidos",sales=sales).id)==[2,1]
