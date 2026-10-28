from copy import deepcopy
from types import SimpleNamespace
import pytest
import requests
import bodega.auth as auth
import bodega.shared_cart as shared
from bodega.repository import DataError


class RerunSignal(BaseException):
    pass


def response(data, status=200):
    return SimpleNamespace(ok=200 <= status < 300, status_code=status, json=lambda: data)


@pytest.fixture
def session(monkeypatch):
    values={"identity":{"token":"old-web-token","refresh_token":"web-refresh",
        "uid":"owner","email":"owner@test.invalid","role":"administrador","expires_at":990,"started":1}}
    settings={"FIREBASE_API_KEY":"public-test-key","FIREBASE_PROJECT_ID":"project-test",
        "SUPABASE_URL":"https://test.invalid","user_roles":{"owner@test.invalid":"administrador","other@test.invalid":"cajero"}}
    monkeypatch.setattr(auth.st,"session_state",values)
    monkeypatch.setattr(auth,"setting",lambda name,default=None:settings.get(name,default))
    monkeypatch.setattr(auth,"mode",lambda:"cloud")
    monkeypatch.setattr(auth.time,"time",lambda:1000)
    monkeypatch.setattr(auth.st,"rerun",lambda **kwargs: (_ for _ in ()).throw(RerunSignal()))
    return values


def claims(uid="owner",email="owner@test.invalid"):
    return {"uid":uid,"email":email,"email_verified":True,"exp":4600}


def test_expiring_token_renews_once_per_execution_without_password(session,monkeypatch):
    calls=[];verified=[]
    def post(url,**kwargs):
        calls.append((url,kwargs))
        return response({"id_token":"new-web-token","refresh_token":"rotated-web-refresh","expires_in":"3600"})
    monkeypatch.setattr(auth.requests,"post",post)
    monkeypatch.setattr(auth,"verify",lambda token:verified.append(token) or claims())
    with auth.identity_scope():
        assert auth.require_identity()["token"]=="new-web-token"
        auth.require_identity()
    assert len(calls)==1 and verified==["new-web-token"]
    assert calls[0][0]=="https://securetoken.googleapis.com/v1/token"
    assert calls[0][1]["data"]=={"grant_type":"refresh_token","refresh_token":"web-refresh"}
    assert session["identity"]["refresh_token"]=="rotated-web-refresh"
    assert "password" not in session["identity"]


def test_valid_web_token_does_not_request_a_refresh(session,monkeypatch):
    session["identity"]["expires_at"]=4600
    monkeypatch.setattr(auth,"verify",lambda token:claims())
    monkeypatch.setattr(auth.requests,"post",lambda *a,**k:pytest.fail("No debe renovar un token vigente"))
    assert auth.require_identity()["uid"]=="owner"


@pytest.mark.parametrize("status",[400,401])
def test_rejected_refresh_requires_access_and_never_reuses_invalid_token(session,monkeypatch,status):
    monkeypatch.setattr(auth.requests,"post",lambda *a,**k:response({},status))
    monkeypatch.setattr(auth,"verify",lambda token:pytest.fail("No verificar el token vencido después del rechazo"))
    with pytest.raises(auth.AccessError):auth.require_identity()
    assert session["identity"]["token"]=="old-web-token"


def test_refresh_cannot_switch_identity(session,monkeypatch):
    monkeypatch.setattr(auth.requests,"post",lambda *a,**k:response({"id_token":"other-token"}))
    monkeypatch.setattr(auth,"verify",lambda token:claims("other","other@test.invalid"))
    with pytest.raises(auth.AccessError,match="inconsistente"):auth.require_identity()
    assert session["identity"]["uid"]=="owner" and session["identity"]["token"]=="old-web-token"


@pytest.mark.parametrize("status",[429,500,503])
def test_transient_refresh_keeps_pending_order_and_skips_private_work(session,monkeypatch,status):
    session["active_charge"]={"id":"original-order"};original=deepcopy(session)
    monkeypatch.setattr(auth.requests,"post",lambda *a,**k:response({},status))
    warnings=[];monkeypatch.setattr(auth.st,"warning",warnings.append)
    @auth.web_session_guard
    def background():pytest.fail("No debe operar sin comprobar la sesión")
    background()
    assert session==original and len(warnings)==1


def test_refresh_connection_failure_is_recoverable(session,monkeypatch):
    def unavailable(*a,**k):raise requests.ConnectionError("PRIVATE NETWORK DETAIL")
    monkeypatch.setattr(auth.requests,"post",unavailable)
    with pytest.raises(auth.AuthUnavailable) as exc:auth.require_identity()
    assert "PRIVATE" not in str(exc.value) and session["identity"]["uid"]=="owner"


def test_autonomous_cart_fragment_redirects_before_private_request(session,monkeypatch):
    session["identity"].pop("refresh_token")
    session["pending_sale"]={"op":"same-operation","items":[{"producto_id":1,"cantidad":1}]}
    session["cart"]=[{"producto_id":1,"cantidad":1}]
    session["login_password"]="must-not-be-preserved"
    def expired(token):raise auth.AccessError("La sesión no es válida")
    monkeypatch.setattr(auth,"verify",expired)
    monkeypatch.setattr(shared,"available",lambda repo:pytest.fail("No consultar disponibilidad con una sesión inválida"))
    with pytest.raises(RerunSignal):shared._monitor(object())
    assert "identity" not in session and "login_password" not in session
    assert session["login_resume"]["state"]["pending_sale"]["op"]=="same-operation"
    assert "token" not in repr(session["login_resume"])
    assert session["login_notice"]


@pytest.mark.parametrize("same_user",[True,False])
def test_reauthentication_restores_pending_uuid_only_for_original_account(session,monkeypatch,same_user):
    session["pending_sale"]={"op":"same-operation"}
    with pytest.raises(RerunSignal):auth.request_login()
    uid,email=("owner","owner@test.invalid") if same_user else ("other","other@test.invalid")
    monkeypatch.setattr(auth.requests,"post",lambda *a,**k:response({"idToken":"new-access","refreshToken":"new-refresh","expiresIn":"3600"}))
    monkeypatch.setattr(auth,"verify",lambda token:claims(uid,email))
    auth.login(email,"test-password")
    assert session["identity"]["uid"]==uid
    assert (session.get("pending_sale",{}).get("op")=="same-operation") is same_user
    assert "login_resume" not in session


def test_renewed_identity_still_requires_verified_email_and_allowed_role(session,monkeypatch):
    monkeypatch.setattr(auth.requests,"post",lambda *a,**k:response({"id_token":"new-access"}))
    monkeypatch.setattr(auth,"verify",lambda token:{**claims(),"email_verified":False})
    with pytest.raises(auth.AccessError):auth.require_identity()


def test_cart_transport_error_in_background_is_controlled(session,monkeypatch):
    session["identity"]["expires_at"]=4600
    monkeypatch.setattr(auth,"verify",lambda token:claims())
    monkeypatch.setattr(shared,"available",lambda repo:True)
    captions=[];monkeypatch.setattr(auth.st,"caption",captions.append)
    class Repo:
        def shared_read(self):raise DataError("Private network detail",confirmed_rejected=False)
    shared._monitor(Repo())
    assert "identity" in session and len(captions)==1 and "Private" not in captions[0]


def test_logout_affects_only_current_web_session(session,monkeypatch):
    another_device={"token":"mobile-session","uid":"owner"};before=deepcopy(another_device)
    auth.logout()
    assert session=={} and another_device==before


def test_streamlit_fragment_expired_session_returns_to_clean_login(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_MODE","cloud")
    monkeypatch.setattr(auth,"mode",lambda:"cloud")
    monkeypatch.setattr(auth,"setting",lambda name,default=None:"test-project" if name=="FIREBASE_PROJECT_ID" else default)
    def expired(token):raise auth.AccessError("PRIVATE TOKEN ERROR")
    monkeypatch.setattr(auth,"verify",expired)
    app=AppTest.from_string('''
import streamlit as st
from bodega.shared_cart import monitor
if "identity" not in st.session_state:
    st.info(st.session_state.pop("login_notice", "Inicia sesión"))
else:
    monitor(object())
    st.write("Contenido privado")
''')
    app.session_state["identity"]={"uid":"owner","email":"owner@test.invalid","token":"expired"}
    app.session_state["active_charge"]={"id":"keep-original-order"}
    app.run()
    assert not app.exception and not app.error
    assert "identity" not in app.session_state
    assert app.session_state["login_resume"]["state"]["active_charge"]["id"]=="keep-original-order"
    assert any("nuevo acceso" in info.value for info in app.info)
    assert not any("Contenido privado" in item.value for item in app.markdown)


def test_wrong_password_still_shows_a_clear_login_error(monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    root=Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root);monkeypatch.setenv("APP_MODE","cloud")
    def rejected(*a,**k):raise auth.AccessError("No se pudo iniciar sesión. Revisa tu cuenta y contraseña.")
    monkeypatch.setattr(auth,"login",rejected)
    app=AppTest.from_file(root/'app.py').run()
    next(b for b in app.button if b.label=='Ingresar').click().run()
    assert not app.exception
    assert any("cuenta y contraseña" in x.value for x in app.error)
