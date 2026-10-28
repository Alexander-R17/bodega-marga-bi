# Actualizar la caja: Yape por avisos y selección de clientes

Esta entrega corresponde al mismo repositorio Bodega Marga BI y al mismo Supabase. Actualiza el flujo de caja; no migra la aplicación a otra plataforma. No contiene credenciales privadas ni datos nuevos de ejemplo.

## Aplicación de la actualización existente

1. Termina las operaciones pendientes antes de actualizar. Si alguien ya pagó, comprueba ese movimiento; no le solicites otro pago.
2. Descomprime el paquete y sube su contenido a la **raíz del mismo repositorio**, reemplazando los archivos coincidentes. La estructura debe quedar `app.py`, `bodega/`, `database/`, etc.; no pongas una carpeta adicional alrededor.
3. En el SQL Editor del Supabase actual ejecuta **solo `database/10_caja_yape_clientes.sql`** si ya instalaste 06, 07, 08 y 09. No vuelvas a ejecutar el catálogo de demostración ni elimines registros.
4. En Streamlit conserva tus credenciales Firebase y los roles. Al inicio de Secrets, antes de `[firebase_service_account]` y `[user_roles]`, comprueba:

```toml
APP_MODE = "cloud"
SUPABASE_URL = "https://TU_PROYECTO.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "TU_CLAVE_SECRETA_DEL_MISMO_PROYECTO"
CREDIT_ENABLED = true
PAYMENT_NOTIFICATIONS_ENABLED = true
```

Los valores de ejemplo no son claves utilizables. Guarda los Secrets reales y reinicia la app para que también se reconstruya la conexión de la sesión.

5. En **Actividad → Comprobar conexión y permisos de caja → Comprobar Supabase**, entra como administrador y comprueba el resultado. Es una consulta, no crea una venta. Debe indicar versión de caja 10, rol de servidor `service_role` y permisos correctos.
6. Instala y vincula el APK de la versión 0.2 siguiendo `docs/14_INSTALAR_APP_MOVIL.md`. El APK es el mismo ya entregado: esta actualización no exige recompilarlo.

## Cambio del carrito

### Yape

La selección Yape muestra un solo botón **Confirmar venta**. Desaparecen el campo de entidad, el campo de código de operación, la casilla de confirmación manual y el botón alternativo de espera.

Para habilitarlo se exige un receptor vinculado con contacto en los últimos 20 minutos. Un vínculo creado sin importar en Android no cuenta como teléfono conectado. Si ya tienes instalado el lector, pulsa **Comprobar conexión y enviar pendientes** allí, y luego **Actualizar conexión del celular** en el carrito.

Al confirmar se abre un diálogo central que consulta el estado cada 3 segundos. La orden se congela por 120 segundos. **Abre la espera antes de pedir al cliente que pague.** Si llega un único aviso compatible, el servidor vuelve a comprobarlo, espera un margen de observación de cinco segundos desde su recepción y registra la venta, el descuento de stock y el ticket en una transacción. La animación **Cobro registrado con éxito** se muestra después de que el servidor confirme el resultado.

Se exige receptor activo, mismo importe en céntimos, hora posterior a la apertura y dentro de la ventana, recepción en servidor posterior a la apertura, demora del aviso no superior a 30 segundos y ausencia de reutilización. La cerradura del receptor serializa la ingestión y la comprobación final. Los reintentos de la misma orden devuelven la misma venta.

Si faltan avisos, vence la orden, aparecen dos del mismo importe, cambia el stock/precio o hay un problema de servidor, **no se presenta éxito ni se inventa una venta**. Conserva los datos y concilia el movimiento con el administrador. No solicites un segundo pago cuando el cliente ya haya pagado. La espera no reserva inventario.

### Clientes y fiado

- Una venta normal permite buscar clientes por nombre o DNI y seleccionarlos. También muestra a los titulares de fiado, porque sus cuentas usan el mismo directorio de clientes.
- Puedes conservar Consumidor final o escribir los datos de un cliente nuevo. El nuevo cliente identificado se guarda al registrar una venta.
- Al seleccionar **Fiado**, los campos libres de nombre y DNI se sustituyen por el selector de cuentas creadas en Fiados. Es obligatorio elegir al titular; no se selecciona uno automáticamente.
- Nombre y DNI se toman de la cuenta. Se mantienen el límite de crédito, cuenta activa, vencimiento y controles de deuda del servidor.
- El buscador devuelve hasta 75 clientes generales o 100 cuentas por búsqueda. Para encontrar más, escribe parte del nombre o el DNI.
- El DNI conserva ceros iniciales y exige ocho dígitos ASCII. El navegador rechaza la presentación de letras y el servidor vuelve a validar. El formato no comprueba identidad en RENIEC. Los nombres requieren letras y se rechazan caracteres impropios.

Efectivo conserva la confirmación manual. Plin, tarjeta, transferencia y abonos a fiado conservan sus controles anteriores; la detección del lector implementada corresponde al Yape recibido en el teléfono.

## Qué significa el error 401 de la captura

La captura muestra **401**, no permite identificar por sí sola la causa exacta. El paquete distingue:

- Clave rechazada por la API: revisar `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` del mismo proyecto, vigentes y completos. El servidor acepta una clave `sb_secret_...` en `apikey` sin enviarla como JWT, o una legacy `service_role` con su cabecera Bearer.
- Clave legacy con rol `anon` o proyecto diferente: se rechaza antes de efectuar la operación. El análisis local de sus campos solo es diagnóstico; Supabase verifica la firma y vigencia real.
- Respuesta con código PostgreSQL **42501**: permiso SQL insuficiente. SQL 10 vuelve a conceder las operaciones de la aplicación a `service_role`, manteniendo RLS y revocando acceso público, `anon` y `authenticated`.
- Función de caja no encontrada: ejecutar SQL 10, que actualiza también la caché de esquema de PostgREST.

El inicio de sesión Firebase no reemplaza la clave privada de conexión con Supabase. El permiso para leer notificaciones en Android tampoco arregla un 401 de la caja web. No pegues claves privadas ni el JSON de vínculo en un chat, una captura pública o GitHub.

## Alcance de la evidencia del pago

Este es un **piloto de registro basado en avisos del celular**, no una integración oficial con la entidad financiera. Un importe y una hora compatibles no demuestran por sí solos quién pagó ni descartan un abono ajeno del mismo importe que llegue después del margen. El teléfono puede perder notificaciones, estar desconectado o tener una hora incorrecta. Sigue siendo necesaria la conciliación con los movimientos reales del negocio.

Cada venta de este flujo se marca `pago_validacion = AVISO_DISPOSITIVO`; el ticket identifica su referencia como **Referencia interna del aviso**, nunca como número de operación bancaria. Conserva vínculos con aviso, receptor y orden. No se usa `p_revisado = true` para fingir una revisión humana que no ocurrió.

El ticket PDF es interno, no una boleta electrónica SUNAT. No se ha añadido Plin por notificación sin identificar primero la aplicación bancaria receptora.

## Prueba en el negocio

1. Diagnóstico de caja correcto y lector conectado; en Android verifica permisos, lectura activa y conexión correcta.
2. Carrito con importe controlado, Yape y Confirmar venta. Debe verse el diálogo esperando, sin crear todavía una venta.
3. Desde otro teléfono realiza el pago después de abrir el diálogo.
4. Comprueba el movimiento en Yape y el envío del lector. La web debe registrar una sola venta y mostrar la animación después de comprobarla.
5. Verifica stock, Historial de ventas y ticket PDF. Revisa la referencia interna y el tipo de evidencia.
6. Sin hacer otro pago, comprueba búsquedas de clientes y una venta a fiado con una cuenta autorizada.

La prueba física y contra tu proyecto real sigue pendiente; las pruebas automatizadas del paquete usan datos sintéticos y no modifican tu Supabase.

Fuentes oficiales consultadas el 27 de octubre de 2026:

- https://supabase.com/docs/guides/getting-started/api-keys
- https://supabase.com/docs/guides/api/securing-your-api
- https://docs.streamlit.io/develop/api-reference/widgets/st.text_input
