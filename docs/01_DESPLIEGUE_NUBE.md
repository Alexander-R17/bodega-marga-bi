# Publicar Bodega Marga en la nube

Esta entrega contiene código preparado y pruebas locales. No ha creado un nuevo repositorio remoto, ejecutado SQL en tu Supabase ni desplegado tus cuentas. Los pasos siguientes conectan el proyecto a tus servicios. No pegues secretos en un chat o en GitHub.

Si ya publicaste la versión anterior, usa [la guía de actualización](../ACTUALIZAR_DISENO_TIENDA.md). Las instrucciones siguientes corresponden a una instalación nueva.

## 1. Repositorio nuevo

En GitHub crea `bodega-marga-bi` en tu cuenta `Alexander-R17`. Descomprime la entrega y sube **el contenido de `bodega-marga-bi`** al repositorio: `app.py` debe quedar en la raíz, junto a `requirements.txt`, `bodega/` y `database/`. No subas el ZIP como único archivo: Streamlit necesita el código extraído.

Para conservar `.streamlit/` y `.github/`, incluye esas carpetas aunque el explorador no las muestre. La función Upload files de GitHub puede omitir elementos ocultos; revisa que `.streamlit/config.toml` y `.github/workflows/tests.yml` existan tras la carga. Codespaces permite extraer el ZIP y confirmar toda la estructura sin instalación en tu PC.

No copies las carpetas anteriores al repositorio nuevo. Esta entrega sustituye la aplicación energética: así no quedan rutas antiguas, binarios de reportes, controladores PHP ni dependencias huérfanas. Tu repositorio original sirve de respaldo.

## 2. Supabase

Puedes usar tu proyecto existente o uno nuevo para el piloto. Si conservas el existente, el script crea tablas `bodega_*` y deja intactas `dimambiente`, `dimedificio`, `dimocupacion`, `dimtiempo`, `fact_consumo_energetico`, predicciones, sesiones, usuarios y staging del campus.

1. Abre SQL Editor, crea una consulta y ejecuta completo **`database/01_bodega_schema.sql`**.
   A continuación ejecuta **`database/03_catalogo_visual.sql`**, que añade la ficha visual de productos.
   Luego ejecuta **`database/04_galeria_y_bi.sql`**, que añade la galería por URL, el cubo SQL y la medición por sesión.
   Finalmente ejecuta **`database/05_confirmacion_pago.sql`**, que vincula la confirmación manual del pago con el importe y el usuario de caja.
2. Comprueba en Table Editor que existan `bodega_productos`, `bodega_ventas`, `bodega_detalle_venta` y `bodega_movimientos`.
3. Obtén la URL del proyecto y una **clave secreta `sb_secret_...`** en **Settings → API Keys**. Esa clave va exclusivamente en **Secrets del servidor Streamlit**, en `SUPABASE_SERVICE_ROLE_KEY`, nombre que se mantiene por compatibilidad. También se admite una clave legacy `service_role` vigente del mismo proyecto. El cliente envía las claves nuevas mediante `apikey` y reserva `Authorization: Bearer` para las legacy JWT. Las claves públicas `anon` y `sb_publishable_...` no autorizan los objetos privados de esta aplicación.
4. Mantén accesibles las tablas en el esquema `public` para la Data API. El script activa RLS y revoca acceso a `anon` y `authenticated` en los objetos nuevos. El servidor verificado usa `service_role`.
5. Espera unos segundos si la Data API aún no detecta las funciones: el SQL notifica recarga de esquema.

**No ejecutes el esquema que pegaste como contexto.** No era una migración ejecutable y corresponde al dominio energético. Tampoco conviertas sus valores en ventas: kWh no puede transformarse en dinero ni ambientes en productos.

Para una prueba aislada puedes ejecutar `database/02_catalogo_demo_OPCIONAL.sql` y luego importar `data/ventas_demo.csv`. El primer archivo carga productos y stock sintéticos, no la historia de ventas. No lo uses para arrancar el inventario real.

## 3. Firebase Authentication

Se utiliza el proyecto independiente **Bodega Marga BI**, con identificador `bodega-marga-bi`, creado por el propietario para esta tienda. La aplicación web y las credenciales de servidor deben pertenecer a este mismo proyecto. La configuración pública de Hosting y la plantilla de Secrets ya apuntan al nuevo proyecto.

Si vienes de la demostración, sigue primero [Activar el nuevo Firebase y el modo real](07_ACTIVAR_FIREBASE.md). Registrar la aplicación web no configura por sí solo Authentication ni conecta el servidor a Supabase.

1. Abre Authentication → Sign-in method y habilita **Email/Password**.
2. En Users crea las cuentas de propietario, cajero y analista. No se habilita registro público en esta aplicación.
3. En Configuración del proyecto → Cuentas de servicio genera una cuenta de servicio Admin SDK. Guarda el JSON de forma privada.
4. Copia sus campos en `[firebase_service_account]` dentro de Secrets de Streamlit. `private_key` debe conservar los saltos `\n`.
5. Añade cada correo y su rol a `[user_roles]`. Solo se admiten `administrador`, `cajero` y `analista`.
6. En la pantalla de acceso, el usuario escribe su correo y contraseña y pulsa **Enviar correo de verificación**. Después de confirmar el enlace, puede ingresar.

El bloque JavaScript que compartiste es configuración de una aplicación web. Por sí solo no sustituye una cuenta de servicio para verificar tokens desde Python. El servidor comprueba firma, proyecto, expiración, revocación y correo verificado antes de acceder a Supabase. La sesión termina al expirar el token, aproximadamente una hora; el usuario vuelve a iniciar sesión.

No hay integración de identidad Firebase dentro de RLS Supabase en esta versión. La autorización se realiza en el servidor Streamlit y los objetos comerciales solo se conceden a `service_role`. Se trata de un MVP de una tienda con personal autorizado.

## 4. Streamlit Community Cloud

En https://share.streamlit.io inicia sesión con GitHub y elige crear una app:

| Campo | Valor |
|---|---|
| Repository | `Alexander-R17/bodega-marga-bi` |
| Branch | `main` |
| Main file path | `app.py` |
| Python | 3.12 |

En Advanced settings → Secrets pega el contenido de `.streamlit/secrets.toml.example` y sustituye los valores indicados. Publica con:

```toml
APP_MODE = "cloud"
SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "CLAVE_PRIVADA_SOLO_EN_SECRETS"
FIREBASE_API_KEY = "LA_API_KEY_WEB_DE_TU_PROYECTO"
FIREBASE_PROJECT_ID = "bodega-marga-bi"
```

Completa también las secciones `[user_roles]` y `[firebase_service_account]`. Las entradas de cada sección deben quedar debajo de su encabezado TOML; coloca las variables superiores antes de los encabezados.

La aplicación instala `requirements.txt`. Si necesitas cambiar valores, modifica Settings → Secrets y reinicia. No es necesario editar el código para poner claves. Revisa los registros del servicio si muestra error de instalación o permisos; no publiques registros con secretos.

La URL final tendrá el subdominio que asignes, por ejemplo `https://TU-NOMBRE.streamlit.app`. El ejemplo no es una dirección ya creada. Usa la URL que entregue Streamlit.

## 5. Firebase Hosting

Hosting solo sirve `hosting/`: no ejecuta Python ni PHP. El dashboard funciona en Streamlit y la página de Firebase conduce a él. No se integra dentro de un iframe ni se comparten contraseñas mediante URL.

1. Comprueba `hosting/config.js`: `dashboardUrl` ya apunta a `https://bodega-marga-bi.streamlit.app/` y la configuración web corresponde al proyecto Firebase `bodega-marga-bi` proporcionado por el propietario.
2. Abre Cloud Shell de Google, que es el terminal visible en tu captura. Clona el repositorio nuevo. Si es privado, utiliza el método de autenticación que te proporcione GitHub; no introduzcas tokens en comandos que luego publiques.
3. Desde la carpeta del repositorio ejecuta:

```bash
npm install -g firebase-tools
firebase login --no-localhost
firebase deploy --only hosting --project bodega-marga-bi
```

No necesitas ejecutar `firebase init`: esta entrega ya incluye `firebase.json` y `.firebaserc`. Firebase usa el contenido de `hosting/` y las reglas de esa configuración.

**El último comando sustituye el Hosting actual de ese proyecto.** Si deseas conservarlo, crea otro sitio/proyecto Hosting o publica primero un canal de vista previa:

```bash
firebase hosting:channel:deploy bodega-preview --project bodega-marga-bi
```

En una vista previa comprueba el enlace a Streamlit y luego decide cuándo publicar en el dominio principal. Estos comandos se entregan para que el propietario los ejecute; no se han ejecutado contra tu cuenta.

Firebase Analytics se inicializa solo si el visitante acepta medición en la página de entrada. Usa el proyecto y measurement ID proporcionados. Mide esa página y el clic de acceso; no copia ventas de Supabase a Google Analytics ni mide automáticamente todo el dashboard Python. Los eventos internos se almacenan por separado en `bodega_eventos`.

## 6. Comprobación antes del piloto

1. En una base de pruebas crea un producto y registra una entrada de 10 unidades.
2. Como cajero vende 2 unidades. Debe quedar stock 8 y un ticket en el resumen.
3. Como administrador anula ese ticket por error. Debe volver a 10 y desaparecer del ingreso analítico.
4. Prueba una venta superior al stock: debe ser rechazada completamente.
5. Importa un historial pequeño con tickets externos nuevos. El stock actual no debe variar.
6. Reintenta el mismo archivo: debe recuperar el lote existente; un ticket duplicado en otro archivo debe rechazarse.
7. Comprueba que analista no pueda registrar ventas ni editar inventario y que un correo sin rol no pueda acceder.
8. Revisa la tabla y lista de reposición contra un conteo físico antes de usar recomendaciones para comprar.

## Operación cotidiana

La fuente persistente es Supabase. El usuario entra a Streamlit desde Firebase o desde la URL directa; ambos caminos exigen el mismo acceso. Las sugerencias se recalculan al consultar; un pronóstico solo queda persistido cuando se pulsa Guardar.

Un corte de internet impide confirmar operaciones cloud. La interfaz conserva el UUID y los datos de una operación cuya respuesta fue incierta mientras la sesión permanezca abierta; reintenta esa misma operación. Si la sesión se pierde, revisa los tickets y movimientos antes de registrar nuevamente. No existe captura offline ni cola persistente en el dispositivo en este MVP.

Planifica respaldo y recuperación en Supabase según el plan que contrates. Exportar CSV sirve para consultar y conciliar, pero no es una copia completa de la base. La app carga datos paginados en memoria y está orientada a una bodega piloto; una historia mucho mayor requerirá consultas agregadas en el servidor y límites por período.
