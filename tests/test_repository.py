"""Contrato HTTP del servidor: claves nuevas y legacy, sin credenciales reales."""
import json
import pytest
import requests
import bodega.repository as module


def make_repo(monkeypatch, key):
    settings = {"SUPABASE_URL": "  https://example.supabase.co/  ",
                "SUPABASE_SERVICE_ROLE_KEY": key}
    monkeypatch.setattr(module, "setting", lambda name: settings.get(name, ""))
    monkeypatch.setattr(module, "require_identity", lambda: {"uid": "verified-firebase-user"})
    return module.CloudRepository()


def response(status, payload):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(payload).encode()
    return result


@pytest.mark.parametrize("key,uses_bearer", [
    ("sb_secret_TEST_ONLY_NOT_A_REAL_KEY", False),
    ("eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.TEST_ONLY", True),
])
def test_rest_headers_for_server_key_types(monkeypatch, key, uses_bearer):
    repo = make_repo(monkeypatch, "  " + key + "  ")
    captured = {}
    def request(method, url, **kwargs):
        captured.update(method=method, url=url, **kwargs)
        return response(200, [{"id": 1}])
    monkeypatch.setattr(repo.http, "request", request)
    assert repo._request("GET", "bodega_productos", params={"limit": 1}) == [{"id": 1}]
    assert captured["url"] == "https://example.supabase.co/rest/v1/bodega_productos"
    assert captured["headers"]["apikey"] == key
    if uses_bearer:
        assert captured["headers"]["Authorization"] == "Bearer " + key
    else:
        assert "Authorization" not in captured["headers"]


@pytest.mark.parametrize("key,message", [
    ("sb_publishable_TEST_ONLY", "clave secreta"),
    ("sb_secret_TEST\nONLY", "una sola línea"),
    ("", "Configura SUPABASE_URL"),
])
def test_invalid_server_configuration_is_actionable(monkeypatch, key, message):
    with pytest.raises(module.DataError, match=message) as exc:
        make_repo(monkeypatch, key)
    if key:
        assert key not in str(exc.value)


@pytest.mark.parametrize("status", [401, 403])
def test_auth_error_is_actionable_without_echoing_remote_data(monkeypatch, status):
    repo = make_repo(monkeypatch, "sb_secret_TEST_ONLY")
    monkeypatch.setattr(repo.http, "request", lambda *args, **kwargs:
        response(status, {"message": "PRIVATE_DIAGNOSTIC_SHOULD_NOT_BE_DISPLAYED"}))
    with pytest.raises(module.DataError) as exc:
        repo._request("GET", "bodega_productos")
    assert str(status) in str(exc.value)
    assert "service_role" in str(exc.value)
    assert "PRIVATE_DIAGNOSTIC" not in str(exc.value)
    assert repo.key not in str(exc.value)
    assert exc.value.confirmed_rejected


def test_transport_failure_remains_uncertain(monkeypatch):
    repo = make_repo(monkeypatch, "sb_secret_TEST_ONLY")
    def timeout(*args, **kwargs):
        raise requests.Timeout("PRIVATE_TRANSPORT_DETAILS")
    monkeypatch.setattr(repo.http, "request", timeout)
    with pytest.raises(module.DataError) as exc:
        repo._request("POST", "rpc/bodega_registrar_venta", json={})
    assert not exc.value.confirmed_rejected
    assert "PRIVATE_TRANSPORT_DETAILS" not in str(exc.value)


def test_sale_requires_confirmation_before_any_cloud_write(monkeypatch):
    repo=make_repo(monkeypatch,"sb_secret_TEST_ONLY")
    def unexpected(*args,**kwargs):pytest.fail("No debe escribir una venta sin confirmar el pago")
    monkeypatch.setattr(repo,"rpc",unexpected)
    with pytest.raises(module.DataError,match="pago completo"):
        repo.sale("op",[{"producto_id":1,"cantidad":1,"descuento":0}],"Yape")


def test_sale_sends_confirmed_amount_and_verified_actor(monkeypatch):
    repo=make_repo(monkeypatch,"sb_secret_TEST_ONLY")
    monkeypatch.setattr(module,"require_role",lambda *roles:{"uid":"verified-cashier"})
    captured={}
    def request(method,path,**kwargs):
        captured.update(method=method,path=path,**kwargs)
        return {"venta_id":1,"total":4.8}
    monkeypatch.setattr(repo,"_request",request)
    repo.sale("op",[{"producto_id":1,"cantidad":1,"descuento":0}],"Yape",confirmed_total=4.8,reference='TEST-001',entity='YAPE')
    assert captured["path"]=="rpc/bodega_registrar_venta_caja"
    assert captured["json"]["p_pago_confirmado"] is True
    assert captured["json"]["p_total_confirmado"]=="4.8"
    assert captured["json"]["p_usuario"]=="verified-cashier"


def test_legacy_anon_key_is_rejected_before_any_request(monkeypatch):
    import base64
    payload=base64.urlsafe_b64encode(json.dumps({'role':'anon'}).encode()).decode().rstrip('=')
    with pytest.raises(module.DataError,match='clave anon'):
        make_repo(monkeypatch,'eyJhbGciOiJIUzI1NiJ9.'+payload+'.TEST_ONLY')


def test_legacy_key_from_different_project_is_rejected(monkeypatch):
    import base64
    payload=base64.urlsafe_b64encode(json.dumps({'role':'service_role','ref':'otherproject'}).encode()).decode().rstrip('=')
    with pytest.raises(module.DataError,match='proyectos distintos'):
        make_repo(monkeypatch,'eyJhbGciOiJIUzI1NiJ9.'+payload+'.TEST_ONLY')


def test_sql_privilege_error_is_distinguished_from_invalid_key(monkeypatch):
    repo=make_repo(monkeypatch,'sb_secret_TEST_ONLY')
    monkeypatch.setattr(repo.http,'request',lambda *args,**kwargs:response(401,{'code':'42501','message':'PRIVATE'}))
    with pytest.raises(module.DataError,match='42501') as exc:
        repo._request('POST','rpc/bodega_registrar_venta_caja')
    assert '10_caja_yape_clientes.sql' in str(exc.value) and 'PRIVATE' not in str(exc.value)


def test_notice_confirmation_uses_verified_cashier_without_manual_approval(monkeypatch):
    repo=make_repo(monkeypatch,'sb_secret_TEST_ONLY')
    monkeypatch.setattr(module,'require_role',lambda *roles:{'uid':'verified-cashier'})
    captured={}
    def request(method,path,**kwargs):
        captured.update(path=path,**kwargs);return {'estado':'DETECTADO'}
    monkeypatch.setattr(repo,'_request',request)
    repo.confirm_charge_notice('test-operation')
    assert captured['path']=='rpc/bodega_confirmar_cobro_aviso'
    assert captured['json']=={'p_id':'test-operation','p_usuario':'verified-cashier'}
