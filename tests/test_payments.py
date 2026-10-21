import pytest
from bodega.demo import DemoRepository
from bodega.repository import DataError
from bodega.payments import confirmed_amount


@pytest.mark.parametrize("amount", [None, False, True, -1, "NaN", "Infinity", "4.801"])
def test_unconfirmed_or_invalid_payment_never_changes_demo_stock(amount):
    repo=DemoRepository();stock=repo.products[0]["stock"];count=len(repo.headers)
    with pytest.raises(DataError):
        repo.sale("payment",[{"producto_id":1,"cantidad":1,"descuento":0}],"Yape",confirmed_total=amount)
    assert repo.products[0]["stock"]==stock and len(repo.headers)==count


def test_price_change_after_payment_confirmation_leaves_no_sale_or_operation():
    repo=DemoRepository();stock=repo.products[0]["stock"];count=len(repo.headers)
    paid=repo.products[0]["precio"];repo.products[0]["precio"]+=1
    with pytest.raises(DataError,match="total cambió"):
        repo.sale("payment",[{"producto_id":1,"cantidad":1,"descuento":0}],"Efectivo",confirmed_total=paid)
    assert repo.products[0]["stock"]==stock and len(repo.headers)==count
    assert "payment" not in repo.operations


def test_zero_total_can_be_explicitly_confirmed():
    assert confirmed_amount(0)==0
