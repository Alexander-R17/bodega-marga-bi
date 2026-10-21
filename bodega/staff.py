"""Nombres para presentación; el UID sigue siendo la clave de auditoría."""
import unicodedata
import streamlit as st
from bodega.auth import AccessError, firebase_app, require_identity, require_role
from bodega.config import mode, setting

ROLE_LABELS = {"administrador": "Administrador", "cajero": "Cajero", "analista": "Analista"}


def assigned_roles():
    return {str(email).strip().lower(): role for email, role in dict(setting("user_roles", {})).items()
            if role in ROLE_LABELS}


@st.cache_data(ttl=60, max_entries=128, show_spinner=False)
def _profiles(project_id, identifiers, by_email=False):
    # El proyecto forma parte de la clave de caché. Firebase no garantiza el orden de retorno.
    from firebase_admin import auth
    result = {}
    kind = auth.EmailIdentifier if by_email else auth.UidIdentifier
    for start in range(0, len(identifiers), 100):
        response = auth.get_users([kind(value) for value in identifiers[start:start+100]], app=firebase_app())
        for user in response.users:
            result[user.uid] = {"name": (user.display_name or "").strip(),
                                "email": (user.email or "").strip().lower()}
    return result


def profiles_for(uids):
    require_identity()
    identifiers = tuple(sorted({str(uid) for uid in uids if uid}))
    if not identifiers:
        return {}
    try:
        return _profiles(str(setting("FIREBASE_PROJECT_ID")), identifiers)
    except Exception:
        # No atribuir registros a otra cuenta ni bloquear la caja por un fallo del directorio.
        return {}


def session_name():
    identity = st.session_state.get("identity", {})
    if mode() == "demo":
        return "Administrador de demostración"
    profile = profiles_for([identity.get("uid")]).get(identity.get("uid"), {})
    return profile.get("name") or "Nombre pendiente"


def present_activity(data):
    """Copia legible para pantalla/CSV, sin modificar los datos usados por BI."""
    uid_columns = {"usuario_uid": "Responsable", "pago_confirmado_por": "Pago confirmado por"}
    available = [column for column in uid_columns if column in data.columns]
    if not available:
        return data.copy()
    result = data.copy()
    uids = [str(value) for column in available for value in result[column].dropna().unique() if value]
    profiles = {} if mode() == "demo" else profiles_for(uids)
    roles = assigned_roles() if mode() != "demo" else {}
    def person(uid):
        if not uid:
            return "Sin registro"
        if mode() == "demo" and uid == "demo":
            return "Administrador de demostración"
        return profiles.get(uid, {}).get("name") or "Usuario sin nombre"
    def role(uid):
        if mode() == "demo" and uid == "demo":
            return "Administrador"
        email = profiles.get(uid, {}).get("email", "")
        return ROLE_LABELS.get(roles.get(email), "Sin rol asignado")
    for column in available:
        values = result[column].fillna("").astype(str)
        position = list(result.columns).index(column)
        result.insert(position, uid_columns[column], values.map(person))
        if column == "usuario_uid":
            result.insert(position+1, "Rol actual", values.map(role))
        result = result.drop(columns=column)
    result = result.rename(columns={"pago_confirmado_en": "Pago confirmado el",
                                    "pago_confirmado_total": "Importe confirmado"})
    first = [column for column in ("id", "fecha_hora", "fecha", "Responsable", "Rol actual") if column in result]
    return result[first + [column for column in result if column not in first]]


def team_directory():
    require_role("administrador")
    try:
        profiles = _profiles(str(setting("FIREBASE_PROJECT_ID")), tuple(sorted(assigned_roles())), True)
    except Exception:
        raise AccessError("No se pudo leer el equipo en Firebase. Revisa el permiso de lectura de usuarios de la cuenta de servicio.") from None
    return profiles


def save_staff_name(uid, name):
    require_role("administrador")
    name = " ".join(str(name).split())
    if not 2 <= len(name) <= 80 or any(unicodedata.category(c).startswith("C") for c in name):
        raise AccessError("Escribe un nombre de 2 a 80 caracteres, sin caracteres de control.")
    # El destino se comprueba en el servidor; solo cuentas del equipo configurado.
    if uid not in team_directory():
        raise AccessError("Selecciona una cuenta del equipo con rol asignado.")
    from firebase_admin import auth
    try:
        auth.update_user(uid, display_name=name, app=firebase_app())
    except Exception:
        raise AccessError("No se pudo guardar el nombre en Firebase. Revisa el permiso de actualización de usuarios de la cuenta de servicio.") from None
    _profiles.clear()


def team_editor():
    with st.expander("Equipo y nombres"):
        st.caption("Asigna el nombre que aparecerá en la sesión y en los movimientos anteriores y nuevos. El rol se administra en Secrets.")
        if mode() == "demo":
            st.info("Los nombres del equipo se administran en el modo nube.")
            return
        try:
            people = team_directory()
            if not people:
                st.info("No se encontraron cuentas de Firebase para los correos con rol asignado.")
                return
            roles = assigned_roles()
            uid = st.selectbox("Cuenta del equipo", list(people), key="team_member",
                format_func=lambda value: f'{people[value]["email"]} · {ROLE_LABELS.get(roles.get(people[value]["email"]), "Sin rol")}')
            with st.form(f"staff_name_{uid}"):
                name = st.text_input("Nombre para mostrar", value=people[uid]["name"], max_chars=80,
                                     placeholder="Ejemplo: Alexander")
                submitted = st.form_submit_button("Guardar nombre", type="primary")
            if submitted:
                save_staff_name(uid, name)
                st.session_state["flash"] = "Nombre del responsable actualizado."
                st.rerun()
        except AccessError as exc:
            st.error(str(exc))
