# Actualizar nombres, confirmación de pago y vista limpia

Esta actualización usa tu mismo GitHub, Firebase y Supabase. Conserva el diseño de la tienda y los registros existentes. No requiere cambiar los Secrets que ya funcionan.

## 1. Actualiza el repositorio

Descomprime `Bodega_Marga_Usuarios_Pago_Interfaz.zip`. En el repositorio `Alexander-R17/bodega-marga-bi`, sube el **contenido** de la carpeta `actualizacion`, respetando sus rutas. `app.py` queda en la raíz; `staff.py`, `payments.py`, `storefront.py`, `repository.py`, `demo.py` y `bi_pages.py` quedan dentro de `bodega/`. Los archivos de `assets/`, `database/`, `hosting/`, `tests/` y `docs/` mantienen sus carpetas.

Incluye `.streamlit/config.toml` en su carpeta. Si el selector de archivos de tu equipo no muestra esta carpeta, abre el archivo existente en GitHub y añade al final:

```toml
[client]
toolbarMode = "minimal"
```

Si `[client]` ya existe, añade solo `toolbarMode` dentro de esa sección. El archivo es `config.toml`; no reemplaces tus Secrets privados con este contenido.

## 2. Actualiza Supabase

Abre **SQL Editor → New query**, pega y ejecuta el archivo completo `database/05_confirmacion_pago.sql`. Es el único SQL nuevo que necesitas si ya aplicaste 01, 03 y 04. Puedes repetirlo sin duplicar columnas ni borrar información. No vuelvas a cargar el catálogo demo sobre tu inventario real.

Esta migración añade la confirmación manual del pago y su responsable. Si el total calculado por Supabase difiere del que confirmó el cajero, revierte venta, detalle y movimiento de stock juntos. Las ventas anteriores mantienen los campos de confirmación vacíos; no se inventan pagos históricos.

## 3. Reinicia y asigna los nombres

Desde el panel `https://share.streamlit.io/`, abre la administración de tu app y pulsa **Reboot** tras subir los archivos y aplicar el SQL. Entra con tu cuenta administradora y abre **Actividad → Equipo y nombres**.

Selecciona tu correo, escribe **Alexander** y pulsa **Guardar nombre**. Repite para cada empleado, usando su cuenta y su nombre. El nombre se guarda como `display_name` en Firebase Authentication; el rol continúa siendo el asignado en `[user_roles]` de Secrets. Solo el administrador puede usar este editor.

La cabecera mostrará, por ejemplo, **Alexander · Administrador**. Las tablas y su descarga CSV mostrarán **Responsable** y **Rol actual**. Los nombres se resuelven por el UID de cada registro, también para movimientos anteriores. Supabase conserva los UIDs originales como identificadores de auditoría. El nombre y el rol visibles son los actuales, no una fotografía histórica.

Si una cuenta no tiene nombre, se eliminó o el directorio no está disponible, aparece **Usuario sin nombre**; no se atribuye el movimiento a quien esté mirando. Una actualización hecha fuera de la app puede tardar hasta un minuto en reflejarse. Si el editor indica falta de permisos, revisa en Google Cloud IAM que la cuenta de servicio configurada tenga `firebaseauth.users.get` y `firebaseauth.users.update` para este proyecto.

## 4. Prueba el cobro

Agrega un producto al carrito. Escoge Efectivo, Yape, Plin, Tarjeta o Transferencia. Revisa el importe y comprueba que el dinero ingresó en la caja, billetera, POS o cuenta del negocio. Marca **Confirmo que recibí S/ … por …**. Solo entonces se habilita **Confirmar venta**.

Cambiar artículos, cantidades, descuentos, precios o medio de pago reinicia la confirmación. La aplicación bloquea el registro si falta la confirmación, incluso en la capa del repositorio. Si se pierde la respuesta después de enviar la venta, usa **Reintentar venta pendiente**: conserva la operación y no vuelvas a cobrar. En **Actividad → Ventas y pagos** verás quién confirmó y cuándo.

Esta es una verificación manual del cajero. La app no consulta bancos, Yape o Plin ni valida un voucher automáticamente; eso requiere integrar un proveedor de pagos y verificar su respuesta desde el servidor.

## 5. Abre la tienda con la vista limpia

Usa este enlace:

https://bodega-marga-bi.streamlit.app/?embed=true

El estilo oculta el encabezado técnico de Streamlit y conserva la navegación de la tienda y **Mi sesión → Cerrar sesión**. El parámetro oficial `embed=true` elimina la barra, la línea superior y el pie del contenedor de Streamlit. El panel de administración del propietario sigue accesible desde Streamlit Community Cloud. Si al abrir tu enlace habitual aparece **Manage app**, abre el enlace limpio anterior.

`hosting/config.js` ya apunta al enlace limpio. Si publicaste la portada en Firebase Hosting, vuelve a desplegar `hosting/` para actualizar su botón. La aplicación Python continúa ejecutándose en Streamlit.

Referencias oficiales: [nombres de usuarios en Firebase](https://firebase.google.com/docs/auth/admin/manage-users), [vista embed de Streamlit](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app/embed-your-app).
