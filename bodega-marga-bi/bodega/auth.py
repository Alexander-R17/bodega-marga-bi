import time
import requests
import streamlit as st
from bodega.config import setting


class AccessError(Exception):
    pass


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
    st.session_state["identity"] = {"token": token, "uid": claims["uid"],
                                    "email": claims["email"], "role": role,
                                    "started": time.time()}


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
    # Duración máxima del token ~1 h; se solicita un nuevo acceso al expirar.
    claims = verify(identity["token"])
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
