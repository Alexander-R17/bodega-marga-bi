# Activar el nuevo Firebase y el modo real

Proyecto Firebase: **Bodega Marga BI** (`bodega-marga-bi`). Aplicación Streamlit: `https://bodega-marga-bi.streamlit.app/`.

La aplicación web ya fue registrada por el propietario. El bloque `firebaseConfig` se incorporó a `hosting/config.js` y al ejemplo de Secrets. La portada conserva la medición opcional mediante consentimiento. El SDK web se carga desde los módulos CDN existentes: este proyecto no necesita incorporar el ejemplo npm a `app.py`.

Estos cambios están preparados en los archivos de esta entrega. No crean usuarios, no instalan credenciales privadas, no modifican Secrets y no publican Hosting en las cuentas del propietario.

## 1. Crear la cuenta de la tienda

En el nuevo proyecto abre **Authentication**. En **Método de acceso / Sign-in method**, habilita **Correo electrónico/contraseña**. En **Usuarios**, crea la cuenta de propietario con su correo y una contraseña elegida en la consola. Usa ese mismo correo en `[user_roles]` con el rol `administrador`.

La sección **Usuarios y permisos** de Configuración del proyecto administra colaboradores de Firebase. Las cuentas de la tienda pertenecen a Authentication.

## 2. Preparar Secrets de Streamlit

Abre tu aplicación en el panel de Streamlit Community Cloud y entra a **Settings → Secrets**. Si no encuentras Settings, abre **Manage app** y su menú de administración.

Copia la estructura siguiente y completa todos los marcadores antes de guardar. Usa la URL y la clave legacy `service_role` de tu proyecto Supabase de Bodega Marga, compatibles con el cliente actual. El JSON de cuenta de servicio es el que descargaste del nuevo Firebase. Sus campos se copian dentro de `[firebase_service_account]`.

```toml
APP_MODE = "cloud"
SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "PEGA_TU_SERVICE_ROLE_DE_SUPABASE"
FIREBASE_API_KEY = "AIzaSyB8LEzU5myjycWzufZSUtC0Y_-HrtNDyOI"
FIREBASE_PROJECT_ID = "bodega-marga-bi"

[user_roles]
"TU_CORREO_CREADO_EN_AUTHENTICATION" = "administrador"

[firebase_service_account]
type = "service_account"
project_id = "bodega-marga-bi"
private_key_id = "COPIA_private_key_id_DEL_JSON"
private_key = "COPIA_EL_VALOR_COMPLETO_DE_private_key_DEL_JSON"
client_email = "COPIA_client_email_DEL_JSON"
client_id = "COPIA_client_id_DEL_JSON"
token_uri = "https://oauth2.googleapis.com/token"
```

Para `private_key`, copia el valor completo del JSON entre comillas dobles, incluido `-----BEGIN PRIVATE KEY-----`, los separadores `\n` y `-----END PRIVATE KEY-----`. Un TOML con comillas dobles interpreta los escapes `\n`; no pegues la clave con saltos físicos dentro de una cadena de una sola línea. El servidor también admite los separadores `\n` que hayan quedado literales.

Las variables generales van antes de `[user_roles]` y `[firebase_service_account]`. Cada encabezado cambia la sección de las líneas siguientes. Reemplaza el correo de ejemplo por el correo exacto de Authentication. Para añadir personal, los roles admitidos son `administrador`, `cajero` y `analista`.

El JSON Admin y la clave `service_role` son privados y se colocan en Secrets del servidor. No se suben a GitHub, a Hosting ni al chat. Las contraseñas de las cuentas tampoco se colocan en Secrets.

## 3. Ingresar y verificar el correo

Guarda Secrets y reinicia la app desde **Reboot app** si el servicio no se reinicia automáticamente. La pantalla debe mostrar el formulario de acceso y dejar de presentar la banda de demostración.

Introduce el correo y la contraseña de la cuenta creada en Authentication. Si el correo aún no está verificado, pulsa **Enviar correo de verificación**, abre el enlace recibido y vuelve a iniciar sesión. La cuenta necesita correo verificado y rol asignado. El proyecto del token, el JSON y `FIREBASE_PROJECT_ID` deben coincidir con `bodega-marga-bi`.

## 4. Comprobar que los datos son persistentes

Comprueba que Supabase tiene las tablas `bodega_*` y las migraciones `01`, `03` y `04`. El cambio de Firebase no requiere una migración SQL adicional.

Los productos, fotos y ventas que solo existían en una sesión demo no se transfieren automáticamente. Registra el catálogo y el conteo inicial de la bodega. Si ya hay datos de pruebas en Supabase, identifica su origen antes de iniciar el piloto y acuerda cómo separarlos.

En una prueba controlada, registra un producto, una entrada de 10 unidades y una venta de 2. Deben quedar 8 unidades y un ticket con sus líneas. Cierra sesión, vuelve a entrar y comprueba que el stock y la venta persisten y coinciden con BI. La anulación del ticket debe restituir las unidades y excluir su ingreso del tablero. Comprueba también que una cuenta analista no pueda vender y que un correo sin rol no acceda.

## 5. Publicar la portada en Firebase

Una vez validado el acceso real, publica `hosting/` en el proyecto `bodega-marga-bi`, siguiendo [01_DESPLIEGUE_NUBE.md](01_DESPLIEGUE_NUBE.md). La portada abre la aplicación Streamlit mediante su botón. Firebase Hosting sirve la portada y Streamlit ejecuta Python.

Antes de publicar en el dominio principal puedes revisar un canal de vista previa. El acceso público a la portada no elimina la autenticación de la tienda.
