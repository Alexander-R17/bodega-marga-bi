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
    from psycopg.conninfo import conninfo_to_dict
    config=conninfo_to_dict(dsn)
    if config.get('host') not in {'127.0.0.1','localhost','::1'} or config.get('dbname')!='bodega_test':
        pytest.skip('Integración destructiva restringida a PostgreSQL local desechable bodega_test; nunca Supabase.')
    conn=psycopg.connect(dsn,autocommit=True)
    # Solo para una base nueva de pruebas. Jamás usar un DSN productivo.
    conn.execute("DO $$ BEGIN CREATE ROLE anon; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    conn.execute("DO $$ BEGIN CREATE ROLE authenticated; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    conn.execute("DO $$ BEGIN CREATE ROLE service_role BYPASSRLS; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    conn.execute((ROOT/"database/01_bodega_schema.sql").read_text())
    conn.execute((ROOT/"database/01_bodega_schema.sql").read_text())
    conn.execute((ROOT/"database/03_catalogo_visual.sql").read_text())
    conn.execute((ROOT/"database/03_catalogo_visual.sql").read_text())
    conn.execute((ROOT/"database/04_galeria_y_bi.sql").read_text())
    conn.execute((ROOT/"database/04_galeria_y_bi.sql").read_text())
    conn.execute((ROOT/"database/05_confirmacion_pago.sql").read_text())
    conn.execute((ROOT/"database/05_confirmacion_pago.sql").read_text())
    for name in ['06_clientes_historial_ticket.sql','07_piloto_avisos_yape.sql','08_fiado.sql','09_espera_cobros.sql','10_caja_yape_clientes.sql']:
        conn.execute((ROOT/'database'/name).read_text())
        conn.execute((ROOT/'database'/name).read_text())
    conn.execute("TRUNCATE bodega_cobros,bodega_pago_avisos,bodega_pago_dispositivos,bodega_referencias_pago,bodega_fiado_cuentas,bodega_clientes,bodega_productos,bodega_categorias,bodega_proveedores,bodega_tiempo,bodega_ventas,bodega_detalle_venta,bodega_movimientos,bodega_operaciones,bodega_staging,bodega_lotes,bodega_predicciones,bodega_eventos,bodega_reposiciones RESTART IDENTITY CASCADE")
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
    with pytest.raises(psycopg.Error):db.execute("select bodega_guardar_producto_catalogo('{}'::jsonb)")


def test_db_credit_limit_serializes_two_cashiers(db):
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    account=db.execute("select bodega_configurar_fiado('12345678','Cliente prueba',5,true,'admin')").fetchone()[0]['cuenta_id']
    due=db.execute("select (now() at time zone 'America/Lima')::date+7").fetchone()[0]
    def buy(_):
        with psycopg.connect(os.environ['TEST_DATABASE_URL'],autocommit=True) as conn:
            try:
                return conn.execute("select bodega_vender_fiado(%s,%s::jsonb,%s,%s,4.8,'cashier')",(
                    uuid4(),json.dumps([{'producto_id':1,'cantidad':1,'descuento':0}]),account,due)).fetchone()[0]
            except psycopg.Error:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(buy,range(2)))
    assert sum(x is not None for x in results)==1
    assert db.execute('select stock from bodega_productos where id=1').fetchone()[0]==7
    assert float(db.execute('select bodega_saldo_fiado(%s)',(account,)).fetchone()[0])==4.8


def test_db_wait_dedup_never_registers_without_review(db):
    from datetime import datetime,timezone
    import psycopg
    device=uuid4();charge=uuid4();hash='a'*64
    db.execute("select bodega_vincular_receptor(%s,'Receptor prueba',%s,'admin')",(device,hash))
    db.execute("select bodega_abrir_cobro(%s,%s,%s::jsonb,'{}',4.8,'cashier')",(charge,device,json.dumps([{'producto_id':1,'cantidad':1,'descuento':0}])))
    event={'event_id':'b'*64,'package':'com.bcp.innovacxion.yapeapp','amount_cents':480,'notified_at':datetime.now(timezone.utc).isoformat()}
    for _ in range(2):db.execute('select bodega_recibir_aviso(%s,%s,%s::jsonb)',(device,hash,json.dumps(event)))
    assert db.execute("select bodega_estado_cobro(%s,'cashier')",(charge,)).fetchone()[0]['estado']=='DETECTADO'
    assert db.execute('select count(*) from bodega_ventas').fetchone()[0]==0
    with pytest.raises(psycopg.Error):db.execute("select bodega_finalizar_cobro(%s,'REGISTRAR','TEST-001','YAPE',false,'cashier')",(charge,))


def test_catalog_metadata_preserves_stock_and_historical_sales(db):
    import psycopg
    db.execute("SET ROLE service_role")
    sell(db,uuid4(),[{"producto_id":1,"cantidad":1,"descuento":0}])
    payload={"id":1,"codigo":"7750001000011","nombre":"Arroz extra 1 kg","categoria":"Abarrotes",
        "proveedor":"Proveedor prueba","precio":5.2,"costo":3.6,"stock_minimo":5,"plazo_dias":2,"activo":True,
        "descripcion":"Arroz embolsado","marca":"Marca de prueba","presentacion":"1 kg","imagen_url":"https://example.com/arroz.png"}
    db.execute("select bodega_guardar_producto_catalogo(%s::jsonb)",(json.dumps(payload),))
    assert db.execute("select stock,descripcion,imagen_url from bodega_productos where id=1").fetchone()==(7,"Arroz embolsado","https://example.com/arroz.png")
    assert float(db.execute("select precio_unitario from bodega_detalle_venta").fetchone()[0])==4.8
    payload.update(precio=999,imagen_url="http://example.com/no.png")
    with pytest.raises(psycopg.Error):db.execute("select bodega_guardar_producto_catalogo(%s::jsonb)",(json.dumps(payload),))
    assert float(db.execute("select precio from bodega_productos where id=1").fetchone()[0])==5.2


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


def test_gallery_and_sql_cube_preserve_operational_data(db):
    import psycopg
    db.execute("SET ROLE service_role")
    sell(db,uuid4(),[{"producto_id":1,"cantidad":1,"descuento":0},{"producto_id":4,"cantidad":1,"descuento":0}])
    payload={"id":1,"codigo":"7750001000011","nombre":"Arroz extra 1 kg","categoria":"Abarrotes","proveedor":"Proveedor",
        "precio":4.8,"costo":3.6,"stock_minimo":5,"plazo_dias":2,"activo":True,"imagenes_urls":["https://example.com/1.png","https://example.com/2.png","https://example.com/1.png"]}
    db.execute("select bodega_guardar_producto_galeria(%s::jsonb)",(json.dumps(payload),))
    assert db.execute("select stock,imagen_url,imagenes_urls from bodega_productos where id=1").fetchone()==(7,"https://example.com/1.png",["https://example.com/1.png","https://example.com/2.png"])
    payload.update(precio=999,imagenes_urls=["http://bad.example.com/image.png"])
    with pytest.raises(psycopg.Error):db.execute("select bodega_guardar_producto_galeria(%s::jsonb)",(json.dumps(payload),))
    assert float(db.execute("select precio from bodega_productos where id=1").fetchone()[0])==4.8
    assert db.execute("select tickets from bodega_v_cubo_ventas where mascara_agrupacion=7").fetchone()[0]==1
    db.execute("RESET ROLE; SET ROLE anon")
    with pytest.raises(psycopg.Error):db.execute("select * from bodega_v_cubo_ventas")
    with pytest.raises(psycopg.Error):db.execute("select bodega_guardar_producto_galeria('{}'::jsonb)")


def test_payment_confirmation_is_required_atomic_and_idempotent(db):
    import psycopg
    items=json.dumps([{"producto_id":1,"cantidad":1,"descuento":0}])
    query="select bodega_registrar_venta_pagada(%s,%s::jsonb,'Yape','test',%s,%s)"
    db.execute("SET ROLE service_role")
    for confirmed,total in [(False,4.8),(None,4.8),(True,None),(True,4.7)]:
        with pytest.raises(psycopg.Error):db.execute(query,(uuid4(),items,confirmed,total))
    assert db.execute("select stock from bodega_productos where id=1").fetchone()[0]==8
    assert db.execute("select count(*) from bodega_ventas").fetchone()[0]==0
    assert db.execute("select count(*) from bodega_operaciones where tipo='VENTA'").fetchone()[0]==0
    op=uuid4();first=db.execute(query,(op,items,True,4.8)).fetchone()[0]
    timestamp=db.execute("select pago_confirmado_en from bodega_ventas").fetchone()[0]
    assert db.execute(query,(op,items,True,4.8)).fetchone()[0]==first
    assert db.execute("select stock from bodega_productos where id=1").fetchone()[0]==7
    row=db.execute("select pago_confirmado_por,pago_confirmado_total,pago_confirmado_en from bodega_ventas").fetchone()
    assert row[0]=="test" and float(row[1])==4.8 and row[2]==timestamp
    db.execute("RESET ROLE; SET ROLE anon")
    with pytest.raises(psycopg.Error):db.execute(query,(uuid4(),items,True,4.8))
