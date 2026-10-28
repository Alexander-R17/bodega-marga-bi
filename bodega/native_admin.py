"""Activa el acceso nativo con las mismas cuentas autorizadas de Firebase."""
import io,json
import streamlit as st
from bodega.auth import require_role
from bodega.config import mode,setting
from bodega.staff import team_directory,assigned_roles
from bodega.repository import DataError


def render(repo):
    if mode()!='cloud' or not hasattr(repo,'activate_native'):return
    with st.expander('Activar o actualizar acceso de la app nativa'):
        st.caption('Publica la configuración Firebase pública y sincroniza los UID, nombres y roles ya autorizados. No crea otro Firebase ni copia contraseñas.')
        if st.button('Activar app nativa y sincronizar equipo',key='native_activate'):
            identity=require_role('administrador');people=team_directory();roles=assigned_roles()
            team=[{'uid':uid,'email':p['email'],'nombre':p['name'],'rol':roles[p['email']]} for uid,p in people.items() if p['email'] in roles]
            result=repo.activate_native(str(setting('FIREBASE_PROJECT_ID')),str(setting('FIREBASE_API_KEY')),team)
            st.success(f"App nativa habilitada para {result['cuentas']} cuentas. Repite esta sincronización cuando cambies roles o nombres del equipo.")
        endpoint=repo.url+'/functions/v1/tienda-movil'
        st.code(endpoint,language=None)
        st.caption('En la app nativa: Configurar tienda → pega esta dirección. Si el celular ya tiene el receptor Yape vinculado, detecta automáticamente el proyecto.')
        st.download_button('Descargar configuración pública de la tienda',json.dumps({'endpoint':endpoint}),file_name='tienda_marga_config.json',mime='application/json')
