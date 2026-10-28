import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from copy import deepcopy
import requests
import streamlit as st
from bodega.config import setting, mode


class AccessError(Exception):
    pass


class AuthUnavailable(AccessError):
    """Fallo temporal: conservar la sesión y no ejecutar operaciones privadas."""


_execution = ContextVar("bodega_identity_execution", default=None)


@contextmanager
def identity_scope():
    """Verifica Firebase una vez por ejecución, nunca entre sesiones o reruns."""
    marker = _execution.set({})
    try:
        yield
    finally:
        _execution.reset(marker)


def role_for(claims):
    roles = dict(setting("user_roles", {}))
    normalized = {k.strip().lower(): v for k, v in roles.items()}
    email = str(claims.get("email", "")).strip().lower()
    role = normalized.get(email)
    if not claims.get("email_verified") or role not in {"administrador", "cajero", "analista"}:
        raise AccessError("Tu cuenta necesita correo verificado y un rol asignado por el propietario.")
    return role


@st.cache_resource
def firebase_app():
    import firebase_admin
    from firebase_admin import credentials
    account = dict(setting("firebase_service_account", {}))
    required=("private_key","client_email","token_uri")
    if not all(account.get(k) for k in required) or account.get("project_id") != setting("FIREBASE_PROJECT_ID"):
        raise AccessError("Configura la cuenta de servicio Firebase del mismo proyecto en Secrets.")
    account["private_key"] = account["private_key"].replace("\\n", "\n")
    try:
        return firebase_admin.get_app("bodega-marga")
    except ValueError:
        try:
            return firebase_admin.initialize_app(credentials.Certificate(account), name="bodega-marga")
        except Exception:
            raise AccessError("Revisa el formato y la clave de la cuenta de servicio Firebase en Secrets.") from None


def verify(token):
    from firebase_admin import auth
    try:
        return auth.verify_id_token(token, app=firebase_app(), check_revoked=True)
    except AccessError:
        raise
    except auth.CertificateFetchError:
        raise AuthUnavailable("No se pudo comprobar el acceso. Reintentaremos cuando vuelva la conexión.") from None
    except Exception:
        raise AccessError("La sesión no es válida. Inicia sesión nuevamente.") from None


def login(email, password):
    key = setting("FIREBASE_API_KEY")
    if not key:
        raise AccessError("Falta FIREBASE_API_KEY en Secrets.")
    try:
        response = requests.post(
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
            params={"key": key},
            json={"email": email, "password": password, "returnSecureToken": True}, timeout=20,
        )
    except requests.RequestException:
        raise AccessError("No se pudo contactar con Firebase. Intenta nuevamente.") from None
    if not response.ok:
        raise AccessError("No se pudo iniciar sesión. Revisa tu cuenta y contraseña.")
    token = response.json()["idToken"]
    claims = verify(token)
    role = role_for(claims)
    resume = st.session_state.pop("login_resume", None)
    if resume and resume.get("uid") == claims["uid"] and resume.get("project") == setting("FIREBASE_PROJECT_ID") and resume.get("database") == setting("SUPABASE_URL"):
        st.session_state.update(resume["state"])
    st.session_state["identity"] = {"token": token, "uid": claims["uid"],
                                    "email": claims["email"], "role": role,
                                    "refresh_token": response.json().get("refreshToken", ""),
                                    "expires_at": claims.get("exp", time.time()+int(response.json().get("expiresIn",3600))),
                                    "started": time.time()}


def _renew(identity):
    """Renueva solo esta sesión web; nunca revoca sesiones del celular."""
    try:
        response = requests.post("https://securetoken.googleapis.com/v1/token",
            params={"key": setting("FIREBASE_API_KEY")},
            data={"grant_type":"refresh_token", "refresh_token":identity["refresh_token"]}, timeout=20)
    except requests.RequestException:
        raise AuthUnavailable("No se pudo renovar el acceso. Reintentaremos cuando vuelva la conexión.") from None
    if response.status_code >= 500 or response.status_code == 429:
        raise AuthUnavailable("El servicio de acceso está temporalmente ocupado. Intenta nuevamente.")
    if not response.ok:
        raise AccessError("Tu sesión web necesita un nuevo acceso.")
    try:
        data=response.json();token=data["id_token"]
        expires=time.time()+int(data.get("expires_in",3600))
    except (ValueError, KeyError, TypeError):
        raise AuthUnavailable("No se recibió la renovación del acceso. Intenta nuevamente.") from None
    claims=verify(token);role=role_for(claims)
    if claims.get("uid") != identity["uid"] or claims.get("email","").lower() != identity["email"].lower():
        raise AccessError("Sesión inconsistente.")
    identity.update(token=token, refresh_token=data.get("refresh_token") or identity["refresh_token"],
                    expires_at=claims.get("exp",expires),role=role)
    return claims


def send_verification(email, password):
    key=setting("FIREBASE_API_KEY")
    if not key: raise AccessError("Falta FIREBASE_API_KEY en Secrets.")
    try:
        signed=requests.post("https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
            params={"key":key},json={"email":email,"password":password,"returnSecureToken":True},timeout=20)
        if not signed.ok: raise AccessError("No se pudo autenticar la cuenta para verificarla.")
        sent=requests.post("https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode",
            params={"key":key},json={"requestType":"VERIFY_EMAIL","idToken":signed.json()["idToken"]},timeout=20)
        if not sent.ok: raise AccessError("No se pudo enviar la verificación. Intenta después.")
    except requests.RequestException:
        raise AccessError("No se pudo contactar con Firebase.") from None


def require_identity():
    identity = st.session_state.get("identity")
    if not identity:
        raise AccessError("Inicia sesión para acceder.")
    # Verificación en cada ejecución: revocación, cuenta deshabilitada y expiración.
    # La renovación usa únicamente el refresh token de esta sesión del servidor.
    scope = _execution.get()
    token = identity["token"]
    claims = scope.get(token) if scope is not None else None
    if claims is None:
        if identity.get("refresh_token") and identity.get("expires_at",0) <= time.time()+60:
            claims = _renew(identity)
            token = identity["token"]
        else:
            claims = verify(token)
        if scope is not None:
            scope[token] = claims
    role = role_for(claims)
    if claims["uid"] != identity["uid"]:
        raise AccessError("Sesión inconsistente.")
    identity["role"] = role
    return identity


def require_role(*roles):
    identity = require_identity()
    if identity["role"] not in roles:
        raise AccessError("Tu rol no tiene permiso para esta operación.")
    return identity


def logout():
    st.session_state.clear()


def request_login():
    """Oculta datos y conserva solo operaciones recuperables del mismo UID."""
    identity=st.session_state.get("identity",{})
    keys=("cart","shared_snapshot","shared_upload","previous_local_cart","pending_sale",
          "pending_credit","active_charge","charge_start_candidate","pending_movement",
          "pending_annul","pending_decision","shop_view")
    resume={"uid":identity.get("uid"),"project":setting("FIREBASE_PROJECT_ID"),"database":setting("SUPABASE_URL"),
            "state":{k:deepcopy(st.session_state[k]) for k in keys if k in st.session_state}}
    logout()
    if resume["uid"] and resume["state"]:st.session_state["login_resume"]=resume
    st.session_state["login_notice"]="Tu sesión web necesita un nuevo acceso. Inicia sesión para continuar."
    st.rerun(scope="app")


def web_session_guard(function):
    """Los fragmentos autónomos controlan su propia autenticación y sus errores."""
    @wraps(function)
    def guarded(*args,**kwargs):
        try:
            with identity_scope():
                if mode()!='demo':require_identity()
                return function(*args,**kwargs)
        except AuthUnavailable as exc:
            st.warning(str(exc))
        except AccessError:
            request_login()
    return guarded
