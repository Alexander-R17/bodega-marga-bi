# Instalar el lector en tu Samsung S23 Ultra

Esta es la app **Bodega Marga · Avisos**, versión **0.2-piloto**. Se instala en el celular del negocio que recibe los yapeos. Usa los scripts 07, 09 y la actualización de caja 10 ya preparados y el vínculo creado por tu aplicación web. No hace falta volver a ejecutar esos scripts únicamente para instalar el APK.

El instalador está compilado y su firma fue verificada. Se comprobó el parser con 21 mensajes sintéticos y el contrato del receptor HTTPS con pruebas locales. **Todavía falta la prueba en tu teléfono y tu Supabase.** Es una compilación del proyecto para pruebas, no una app oficial de Yape ni un comprobador directo de saldo bancario.

## 1. Instalar el APK en el teléfono receptor

Descarga **Bodega_Marga_Avisos_Android_v0_2.apk** en el S23 Ultra y ábrelo desde Descargas. Completa la instalación que autorice Android para ese archivo. Después abre **Bodega Marga · Avisos**, con el icono verde y la letra M.

Si Samsung muestra un bloqueo, conserva el mensaje exacto para revisar el ajuste específico. No necesitas instalar otra app bancaria ni entregar contraseñas del banco a este lector.

## 2. Comprobar la conexión del servidor

Además de las tablas SQL, debe existir la función HTTPS:

```text
https://TU_PROYECTO.supabase.co/functions/v1/recibir-aviso-yape
```

Si aún no la desplegaste:

1. En tu Supabase actual abre **Edge Functions → Deploy a new function → Via Editor**.
2. Usa el nombre exacto **recibir-aviso-yape**.
3. Pega el archivo completo `supabase/functions/recibir-aviso-yape/index.ts` incluido en el ZIP de conexión.
4. Despliega la función. Desactiva **Verify JWT with legacy secret** solo para esta función: el propio código valida la credencial revocable del celular. No cambies otras funciones.
5. Las claves de Supabase permanecen en el entorno del servidor. No se introducen en el teléfono.

Subir el TypeScript a GitHub no despliega la función en Supabase.

## 3. Activar la opción en Streamlit

Revisa que los Secrets tengan esta línea **al principio, antes de cualquier bloque `[ ... ]`**:

```toml
PAYMENT_NOTIFICATIONS_ENABLED = true
```

Conserva los otros valores y reinicia Streamlit tras guardarlos. Si la línea estaba en `false`, cámbiala a `true`.

## 4. Crear el archivo que vincula el celular

En la app web, entra como administrador y abre:

**Actividad → Vincular celular receptor para Yape → Crear vínculo privado del celular**.

Pon un nombre como **S23 Ultra · caja**. Descarga el archivo **vinculo_receptor_PRIVADO.json** y transfiérelo de forma privada a ese teléfono. Este JSON es generado por Bodega Marga; **no es el JSON de cuenta de servicio de Firebase**.

El vínculo permite enviar avisos como ese dispositivo. No lo subas a GitHub ni lo publiques. Al terminar la importación elimina el archivo de Descargas y usa la opción de olvidar el vínculo descargable en la sesión web.

## 5. Activar el lector móvil

Dentro de **Bodega Marga · Avisos**:

1. Pulsa **1 · Importar vínculo privado** y selecciona el JSON. Comprueba que la URL corresponda a tu Supabase y confirma.
2. Pulsa **2 · Dar acceso a notificaciones**. En los ajustes de Android autoriza **Bodega Marga: avisos de Yape**.
3. Regresa a la app y marca **3 · Activar lectura y envío de Yape**.
4. Pulsa **Comprobar conexión y enviar pendientes**. Debe indicar **Conexión correcta**.

Android concede un permiso amplio para leer notificaciones. Este código descarta otras aplicaciones antes de leer sus extras y solo procesa el paquete de Yape `com.bcp.innovacxion.yapeapp`. Se envían importe, hora e identificador técnico, sin nombres, texto del aviso ni códigos de seguridad. La credencial se guarda cifrada con Android Keystore. Puedes pausar el lector y revocar el vínculo desde la web.

Si Android muestra específicamente **Ajuste restringido**, consulta **Ajustes → Aplicaciones → Bodega Marga · Avisos → menú de tres puntos → Permitir ajustes restringidos** y vuelve a autorizar el acceso. La disponibilidad y los nombres de esta opción dependen de Android/One UI. El permiso se concede por el propietario del teléfono para el lector propio que está instalando.

En Samsung revisa **Batería → Límites de uso en segundo plano → Apps sin suspensión** y añade el lector. Mantén activas las notificaciones de Yape y la fecha/hora automáticas. La configuración exacta depende de One UI.

## 6. Hacer la primera prueba

1. En la web prepara un carrito con el importe de la prueba y selecciona **Yape**.
2. Pulsa **Actualizar conexión del celular** si hace falta y luego **Confirmar venta**. Se abrirá la ventana central de espera; si hay varios receptores, elige el que utilizarás.
3. Solo después de abrir esa espera, realiza el abono controlado al Yape receptor desde otro celular.
4. Comprueba que el movimiento exista en el Yape receptor. En el lector, pulsa **Actualizar estado**: debe aparecer un aviso reconocido y un envío `SENT`.
5. La ventana comprueba el aviso único y registra la venta automáticamente mediante SQL 10. Debe aparecer **Cobro registrado con éxito** después de recibir confirmación del servidor. Si hay una incidencia o avisos ambiguos, no mostrará éxito: revisa y concilia el movimiento. No se exige ingresar una referencia bancaria en el flujo normal.

La clave del celular autentica al receptor. No es una clave de aprobación bancaria. La deduplicación usa un identificador técnico del aviso, no un número de operación bancaria. Si el aviso no llega o vence la ventana, revisa el movimiento antes de solicitar otro pago.

## Resolver mensajes del lector

| Mensaje | Qué revisar |
| --- | --- |
| Vínculo pendiente | Importar el JSON descargado desde Actividad. |
| Acceso a notificaciones pendiente | Conceder el permiso del paso 2 y regresar al lector. |
| HTTP 404 | Falta desplegar `recibir-aviso-yape` o se importó un proyecto equivocado. |
| HTTP 401/403 | Verificar que el vínculo esté activo y que Verify JWT esté desactivado en esa función. Importar un vínculo nuevo si fue revocado. |
| HTTP 422 o REJECTED | Revisar scripts 07/09, formato y fecha/hora del teléfono. No equivale a que el cliente no pagó. |
| PENDING | El aviso sigue en la cola; comprobar internet, batería y servidor. |
| Formato no reconocido | Se recibió una notificación de Yape que el parser conservador no identifica como recepción. Debe revisarse el formato real sin compartir datos personales ni secretos. |
| SENT y no aparece en la orden | Revisar que el importe sea igual y que la espera se haya abierto antes del abono. Una orden vencida no se recupera con otro cobro al cliente. |

La prueba de conexión confirma una petición HTTPS, no que el permiso siga activo ni que Yape publique todas las notificaciones. El lector no recupera un historial bancario completo si el teléfono estaba apagado o desconectado. La cola conserva reintentos y vence avisos pendientes de más de 24 horas. Plin y transferencias siguen pendientes de identificar y configurar la app bancaria receptora.

## Conservar el código y volver a compilar

Sube a la raíz del GitHub actual la carpeta **android-receptor** y el workflow **.github/workflows/android-receptor.yml** del ZIP. También se incluye el código de conexión de Supabase y esta guía. El ZIP no contiene claves del negocio, JSON de vínculo ni claves privadas de firma.

Puedes abrir `android-receptor` en Android Studio o ejecutar en GitHub Actions **Construir app movil de avisos**. El workflow usa Java 17, Gradle 8.11.1 y las herramientas Android API 35; genera un APK de prueba descargable desde los artefactos de esa ejecución.

La compilación adjunta usa una firma local de piloto. Otra compilación firmada con una clave distinta no puede actualizarla directamente: antes de cambiar de firma hay que revocar el vínculo viejo, desinstalar la app y crear un vínculo nuevo. Una distribución de producción requiere una clave de firma del propietario conservada de forma segura; no se publica en GitHub.

Fuentes oficiales consultadas el 25 de octubre de 2026:

- [Android: NotificationListenerService](https://developer.android.com/reference/android/service/notification/NotificationListenerService)
- [Android: ajustes restringidos](https://support.google.com/android/answer/12623953?hl=es)
- [Samsung: aplicaciones en suspensión](https://www.samsung.com/us/support/answer/ANS10003442/)
