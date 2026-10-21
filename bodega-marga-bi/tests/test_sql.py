"""PostgreSQL real en CI; TEST_DATABASE_URL debe apuntar a una base desechable."""
import os
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import json
import pytest
from pglast import parse_sql

ROOT=Path(__file__).resolve().parents[1]


def test_sql_parses():
    for p in (ROOT/"database").glob("*.sql"):assert parse_sql(p.read_text())


@pytest.fixture
def db():
    import psycopg
    dsn=os.getenv("TEST_DATABASE_URL")
    if not dsn:pytest.skip("TEST_DATABASE_URL no configurada: integración PostgreSQL se ejecuta en GitHub Actions")
    conn=psycopg.connect(dsn,autocommit=True)
    # Solo para una base nueva de pruebas. Jamás usar un DSN productivo.
    conn.execute("DO $$ BEGIN CREATE ROLE anon; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    conn.execute("DO $$ BEGIN CREATE ROLE authenticated; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    conn.execute("DO $$ BEGIN CREATE ROLE service_role BYPASSRLS; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    conn.execute((ROOT/"database/01_bodega_schema.sql").read_text())
    conn.execute((ROOT/"database/01_bodega_schema.sql").read_text())
    conn.execute("TRUNCATE bodega_productos,bodega_categorias,bodega_proveedores,bodega_tiempo,bodega_ventas,bodega_detalle_venta,bodega_movimientos,bodega_operaciones,bodega_staging,bodega_lotes,bodega_predicciones,bodega_eventos,bodega_reposiciones RESTART IDENTITY CASCADE")
    conn.execute((ROOT/"database/02_catalogo_demo_OPCIONAL.sql").read_text())
    yield conn
    conn.close()


def sell(conn,op,items):
    return conn.execute("SELECT bodega_registrar_venta(%s,%s::jsonb,'Efectivo','test')",(op,json.dumps(items))).fetchone()[0]


def test_db_sale_retry_atomic_and_annul(db):
    import psycopg
    items=[{"producto_id":1,"cantidad":2,"descuento":0}];op=uuid4()
    db.execute("SET ROLE service_role")
    first=sell(db,op,items); assert sell(db,op,items)==first
    assert db.execute("select stock from bodega_productos where id=1").fetchone()[0]==6
    with pytest.raises(psycopg.Error):
        sell(db,uuid4(),[{"producto_id":1,"cantidad":1,"descuento":0},{"producto_id":3,"cantidad":1,"descuento":0}])
    assert db.execute("select stock from bodega_productos where id=1").fetchone()[0]==6
    assert db.execute("select count(*) from bodega_ventas").fetchone()[0]==1
    annul=uuid4()
    db.execute("select bodega_anular_venta(%s,%s,'Error caja','test')",(annul,first["venta_id"]))
    db.execute("select bodega_anular_venta(%s,%s,'Error caja','test')",(annul,first["venta_id"]))
    assert db.execute("select stock from bodega_productos where id=1").fetchone()[0]==8
    assert db.execute("select count(*) from bodega_v_ventas").fetchone()[0]==0


def test_db_import_history_and_duplicates(db):
    import psycopg
    row={"ticket":"HIST-1","fecha":"2026-09-01","codigo":"7750001000011","cantidad":100,
         "precio_unitario":"4.80","costo_unitario":"3.60","descuento":"0","medio_pago":"Yape"}
    batch=uuid4()
    db.execute("select bodega_crear_lote(%s,'h.csv',%s,%s::jsonb,'test')",(batch,'a'*64,json.dumps([row])))
    db.execute("select bodega_procesar_lote(%s,'test')",(batch,))
    db.execute("select bodega_procesar_lote(%s,'test')",(batch,))
    assert db.execute("select stock from bodega_productos where id=1").fetchone()[0]==8
    assert db.execute("select count(*) from bodega_v_ventas").fetchone()[0]==1
    second=uuid4()
    db.execute("select bodega_crear_lote(%s,'h2.csv',%s,%s::jsonb,'test')",(second,'b'*64,json.dumps([row])))
    with pytest.raises(psycopg.Error):db.execute("select bodega_procesar_lote(%s,'test')",(second,))
    assert db.execute("select count(*) from bodega_v_ventas").fetchone()[0]==1


def test_db_private_tables_and_rpc(db):
    import psycopg
    db.execute("SET ROLE anon")
    with pytest.raises(psycopg.Error):db.execute("select * from bodega_productos")
    with pytest.raises(psycopg.Error):sell(db,uuid4(),[{"producto_id":1,"cantidad":1,"descuento":0}])


def test_concurrent_sales_cannot_oversell(db):
    import psycopg
    dsn=os.environ["TEST_DATABASE_URL"]
    def attempt():
        with psycopg.connect(dsn,autocommit=True) as c:
            c.execute("SET ROLE service_role")
            try:
                sell(c,uuid4(),[{"producto_id":1,"cantidad":6,"descuento":0}]);return True
            except psycopg.Error:return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:attempt(),range(2)))
    assert sum(results)==1
    assert db.execute("select stock from bodega_productos where id=1").fetchone()[0]==2
