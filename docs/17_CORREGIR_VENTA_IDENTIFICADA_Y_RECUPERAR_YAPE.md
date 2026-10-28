# Corregir el 400 de ventas con DNI y recuperar un cobro recibido

El celular ya reconoce el importe y el servidor acepta su aviso. `SENT: 2` significa dos eventos enviados, no dos ventas registradas. El error sucede después, al guardar la venta. No se debe pedir otro pago.

Se reprodujo en una base local un error del SQL publicado: `42702: column reference "dni" is ambiguous`. La función `bodega_registrar_venta_caja` declaraba una variable `dni` y utilizaba `ON CONFLICT(dni)`, que PostgreSQL no puede resolver de forma inequívoca. Una venta sin DNI podía funcionar, mientras una venta identificada fallaba aunque el importe y el aviso fueran correctos. La captura genérica 400 no identifica por sí sola la causa del proyecto real; el paquete corrige este fallo comprobado y añade códigos seguros para distinguir cualquier otro error.

## Instalar en el proyecto existente

1. Conserva el abono ya recibido. No lo vuelvas a realizar para intentar completar la misma venta.
2. Descomprime el ZIP y sube su contenido a la raíz del mismo repositorio, reemplazando los archivos coincidentes. Cambian `bodega/repository.py` y `bodega/charge_wait.py`; no reemplaces toda la carpeta con archivos vacíos ni elimines los demás módulos.
3. En el SQL Editor del Supabase actual ejecuta **solo `database/11_correccion_clientes_y_conciliacion.sql`**. Las migraciones previas ya deben estar instaladas. SQL 11 no crea ventas al instalarse, no elimina datos ni cambia importes. Se incluye el archivo 06 corregido para nuevas instalaciones; no necesitas volver a ejecutar 06 ahora.
4. Reinicia Streamlit y vuelve a iniciar sesión con la misma cuenta de administrador que abrió la orden fallida.

No hace falta actualizar el APK 0.3, cambiar Secrets ni desplegar otra vez la función de recepción: la entrega y el reconocimiento del aviso ya funcionan.

## Recuperar la venta que ya recibió el pago

1. Si sigue abierto el diálogo anterior, ciérralo y ve a **Actividad**.
2. Abre **Cobros recibidos pendientes de registro** y pulsa **Consultar cobros pendientes**.
3. Selecciona la orden original por su código, cliente e importe. Para el caso actual, identifica la orden de **S/ 4.20**; no elijas la venta anterior de S/ 1.80.
4. Comprueba el movimiento real en el Yape receptor. Marca **Comprobé el movimiento en Yape y corresponde al importe y al cliente de esta orden**.
5. Pulsa **Recuperar venta con el aviso recibido**. Se utiliza el UUID original, el aviso ya asociado y la referencia interna del aviso. El servidor conserva los controles de stock, precios, importe, ventana original y exclusividad de la evidencia. No solicita otro abono.
6. Debe aparecer la orden de venta y el botón de ticket PDF. Revisa **Ventas / Historial de ventas** y el inventario.
7. Si cerraste el cobro antes de recuperar y el carrito todavía contiene esos productos, vacíalo antes de preparar otra venta. El módulo no borra carritos de otras órdenes.

Si la respuesta se pierde, reintenta la misma recuperación. La misma orden devuelve la misma venta; no se registra dos veces ni se descuenta stock dos veces.

La recuperación muestra hasta 50 órdenes propias con aviso ya asociado y sin venta, en estado detectado, vencido o cancelado. No permite convertir una orden sin aviso en una venta pagada. Exige revisión explícita de la persona que concilia y conserva quién lo hizo y cuándo. Si la orden no aparece, no crees otra ni repitas el pago: hay que revisar el estado y la asociación existente.

## Qué cambia y qué se conserva

- Variables internas con prefijo: desaparece la ambigüedad con la columna DNI. La identificación de clientes y su validación continúan activas.
- La consulta de estado conserva como detectada una orden que ya tenía un aviso asociado cuando termina el plazo de espera. Las órdenes antiguas que ya vencieron conservan el aviso y se recuperan mediante revisión explícita.
- Se revisan los candidatos del importe dentro de la ventana original. Si hay varios, el registro se bloquea; no se asigna un abono arbitrario ni se amplía la ventana de coincidencia.
- Se utiliza la venta atómica existente, el mismo UUID y la referencia única del aviso. Un error de stock o precio revierte la transacción completa.
- Las funciones son privadas para el servidor. La interfaz permite recuperar solo al administrador y la base restringe cada orden al usuario original. El listado no devuelve credenciales ni UID de otros usuarios.
- El ticket conserva evidencia de aviso y registra la conciliación manual. Es un ticket interno, no un comprobante tributario ni una respuesta oficial del banco.
- Errores desconocidos muestran únicamente un código diagnóstico permitido, sin exponer el contenido remoto o datos del cliente.

## Verificación

Se probaron en PGlite aislado las ventas consecutivas de S/ 1.80 y S/ 4.20 para el mismo cliente, la recuperación de orden vencida, reintentos sin duplicados, stock y ticket, revisión requerida, usuario correcto, ausencia de aviso, ambigüedad, aviso fuera de tiempo, receptor revocado, acceso privado y repetición de la migración. Las pruebas de interfaz cubren autorización de recuperación, respuesta perdida y conservación de un carrito ajeno.

La corrección todavía debe aplicarse y comprobarse contra el Supabase real del negocio. Ninguna prueba de esta entrega se conectó a la base productiva.

Referencia técnica: https://www.postgresql.org/docs/current/plpgsql-implementation.html
