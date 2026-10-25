# Fiados y espera de pago por orden

Esta actualización mantiene el diseño y la arquitectura de la aplicación publicada. Añade cuentas por cobrar y una ventana de espera para el lector Android de Yape. No migra todavía la interfaz a React ni publica cambios en tus cuentas automáticamente.

## Qué incluye

| Función | Comportamiento |
| --- | --- |
| Fiados | Cuenta por DNI y nombre, límite de crédito y bloqueo de nuevas compras por administrador. |
| Venta a fiado | Registra una venta, descuenta stock y crea una deuda con vencimiento. No marca un pago recibido. |
| Abonos | Permite pagos parciales por venta y conserva medio, referencia, fecha y usuario. No vuelve a generar una venta. |
| Control | Rechaza sobrepagos, referencias repetidas, compras que superan el límite y nuevos fiados con deuda vencida. |
| Anulación | Conserva el historial. Si una venta tiene abonos activos, deben conciliarse y anularse antes de anularla. El sistema no devuelve dinero al banco. |
| Ticket | Identifica la venta a fiado, su vencimiento, lo abonado y el saldo actual. Sigue siendo un ticket interno, no una boleta SUNAT. |
| BI | Página «Fiados y cobranza»: ventas a crédito y abonos del período; cartera y deuda vencida actuales. |
| Espera Yape | Orden de cobro por receptor, ventana con indicador de espera, consulta cada tres segundos y vencimiento a los dos minutos. |
| Avisos ambiguos | Dos avisos candidatos del mismo importe detienen la asociación. No se elige automáticamente el primero. |

Las cuentas de fiado son administradas por el personal de la bodega. Esta entrega no crea un portal para que cada cliente inicie sesión, ni importa deudas antiguas de manera automática.

## Instalar la actualización

1. Descomprime el ZIP. Sube `app.py` y las carpetas completas incluidas a la raíz de tu GitHub actual, conservando rutas como `bodega/credit.py`. No subas solamente los archivos Python de la raíz. La carpeta `bodega` va completa para evitar errores de importación.
2. En Supabase SQL Editor ejecuta, en este orden, los archivos **07, 08 y 09** de `database`. Si aún faltan las funciones de clientes/historial/tickets, ejecuta primero **06**; si ese historial y sus tickets ya funcionan, conserva tu instalación 06. Los archivos 01, 03, 04 y 05 ya deben estar instalados. Actualiza cuando no haya operaciones pendientes en caja. Son migraciones aditivas e idempotentes. No contienen datos de demostración nuevos ni instrucciones para borrar tus productos o ventas.
3. En los Secrets de Streamlit añade al principio, **antes de cualquier bloque `[user_roles]`, `[firebase_service_account]` u otro**, lo siguiente:

```toml
CREDIT_ENABLED = true
PAYMENT_NOTIFICATIONS_ENABLED = false
```

4. Guarda y reinicia Streamlit. Ya puedes usar **Fiados** sin tener el lector Android conectado.
5. Para la espera de Yape, completa la configuración del apartado siguiente y cambia `PAYMENT_NOTIFICATIONS_ENABLED` a `true`, sin comillas. El valor `false` evita consultas al receptor cuando aún no está instalado.

El GitHub revisado incluía código que llama las funciones SQL 06, pero no ese archivo de migración. Por eso se incluye la compatibilidad 06. Las funciones auxiliares ya existentes se conservan cuando sus firmas están presentes.

## Configurar el lector Yape

Se usa el mismo protocolo del APK Android del piloto anterior: `endpoint`, `device_id` y `token`. Esta entrega contiene el servidor y la interfaz de espera; **no incluye un APK Android nuevo**.

1. En tu Supabase actual abre **Edge Functions → Deploy a new function → Via Editor**.
2. Crea **`recibir-aviso-yape`**. Pega el contenido completo de `supabase/functions/recibir-aviso-yape/index.ts` y despliega.
3. En esa función desactiva **Verify JWT with legacy secret**: se autentica con una credencial aleatoria por celular, validada dentro del servidor. No desactives la verificación en otras funciones.
4. El código usa `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` del entorno privado del servidor. No copies esta clave a Android, a un sitio público ni al repositorio.
5. En Streamlit, como administrador, abre **Actividad → Vincular celular receptor para Yape** y crea un vínculo privado.
6. Descarga el JSON, transfiérelo de forma privada al S23 Ultra e impórtalo en el lector Android del piloto. Concede acceso a notificaciones y activa el lector. Elimina después el JSON de Descargas y olvida la copia descargable de la sesión.
7. Mantén activas las notificaciones de Yape y revisa las opciones de suspensión/batería del Samsung. La configuración depende de la versión de One UI.
8. Haz una prueba controlada con el teléfono real antes de usarlo para atender clientes.

Subir un `index.ts` a GitHub no despliega por sí solo una Edge Function. Tampoco basta con encender la opción de Streamlit si no están configurados el servidor y el lector.

## Flujo en caja

Prepara el carrito y selecciona Yape. En **Esperar aviso de Yape en una ventana**, selecciona el receptor y pulsa **Esperar el pago del cliente**. La orden congela artículos, cliente e importe. Mientras está abierta no se permite editar ese carrito.

La ventana muestra el importe y consulta el estado sin recalcular toda la página. Solo se admite una espera activa por receptor. Si aparece un único aviso candidato posterior al inicio de la orden y dentro de su ventana, cambia a **Pago detectado**. Conserva una tolerancia de cinco segundos para diferencias de reloj; esa tolerancia no certifica la hora bancaria. Dos avisos del mismo importe producen **Ambiguo**.

El cajero comprueba el movimiento, ingresa su referencia real y confirma el registro. La venta, su ticket y el consumo de esa orden se guardan en una transacción. Reintentar la misma orden no registra otra venta. La credencial del celular autentica el emisor del aviso; no constituye una aprobación emitida por el banco.

Si vence la espera, se revoca el receptor o se cancela la orden, no se registra una venta. Si el cliente ya pagó, revisa el abono y utiliza la confirmación manual con la referencia correcta: **no solicites otro pago porque haya vencido la ventana**.

La orden no reserva físicamente el inventario. El stock y los precios se validan otra vez al registrar la venta. Si otro movimiento cambió la disponibilidad después del cobro, corresponde conciliar esa situación en caja, sin volver a cobrar al cliente.

## Límites que siguen pendientes

- La fuente actual de avisos es Yape. Para Plin y transferencias hace falta identificar el banco receptor, la aplicación y el formato de sus notificaciones antes de habilitar un lector. No se simula una validación para esos medios.
- Una notificación puede retrasarse, ocultarse, cambiar de formato o no llegar. Una clave propia, el importe y la hora no demuestran por sí solos que un movimiento bancario está liquidado ni que corresponde al comprador actual.
- En efectivo se mantiene la confirmación manual. En los abonos de fiado también se verifica el dinero recibido antes de registrar el abono.
- Los identificadores de avisos son técnicos, no números de operación bancaria. No se reutilizan referencias de pago anuladas para otra venta o abono. Las correcciones que requieren reasignar un movimiento deben conciliarse por administración.
- Las consultas de detalle se limitan a 100 cuentas por búsqueda y 250 cargos/abonos recientes por cuenta; los saldos usan todo su historial. El resumen BI no expone DNI ni nombres a analistas.
- Las tablas de avisos y órdenes conservan trazabilidad. En esta versión no hay una tarea automática de retención para borrar esas órdenes: debe definirse una política antes de un uso prolongado.

## Verificación

Las comprobaciones de SQL usan una base PGlite local desechable. Las pruebas unitarias tienen bloqueado el HTTP externo. Las pruebas PostgreSQL que limpian tablas solo admiten una base local llamada `bodega_test`, creada por el workflow; nunca deben apuntar a Supabase.

```sh
python -m pytest -q
npm ci --prefix validation
npm test --prefix validation
```

La lectura de avisos en el S23 Ultra, la latencia real, la recuperación tras suspensión y el despliegue en tus cuentas siguen requiriendo prueba de integración real. La interfaz se comprobó con AppTest. El navegador automatizado no pudo iniciarse por las restricciones del entorno de ejecución, por lo que no se afirma una validación visual completa en Chrome.
