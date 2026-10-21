# Validación de la entrega

## Verificación ejecutada

Se revisaron las capturas de referencia y se ejecutaron pruebas sobre la versión con diseño de tienda: **33 pruebas correctas, 5 pruebas de PostgreSQL real omitidas por falta de TEST_DATABASE_URL y 18 comprobaciones SQL sobre PostgreSQL embebido correctas**. El proyecto se probó en demostración con datos sintéticos; no se conectó a los servicios del propietario durante estas pruebas.

- Suite Python y Streamlit AppTest: pruebas de navegación, venta desde la interfaz, evaluación/guardado de pronósticos, decisión de reposición, acceso cloud sin fallback, validación CSV, stock, reintentos, exportación segura y permisos de rol.
- SQL ejecutado sobre PostgreSQL embebido mediante PGlite: migración completa reejecutada, catálogo opcional, ventas con `service_role`, reintentos, UUID con payload diferente, rollback de carrito, anulación, carga histórica y duplicados, costo promedio, merma inválida, decisión de reposición, guardado de pronósticos y denegación a `anon`.
- Compilación de módulos Python y revisión sintáctica de JavaScript y scripts SQL.
- Carrito: agregación de un mismo producto, descuentos y totales, límites de stock, cantidades inválidas y retiro de artículos; filtros y ordenamiento del catálogo.
- AppTest: venta con cantidad modificada y Yape; respuesta incierta después de registrar una venta y reintento con el mismo identificador, sin segundo descuento de stock.
- SQL visual: migración adicional ejecutada dos veces, persistencia de descripción y foto sin cambiar stock ni precios históricos, rechazo completo de una foto con URL inválida y denegación de la nueva función a `anon`.

PGlite ejecuta las funciones PL/pgSQL y las transacciones con un motor PostgreSQL embebido; no equivale a probar el servicio Supabase remoto, su Data API o varias conexiones concurrentes. Las cinco pruebas con PostgreSQL real están incluidas y se omiten localmente cuando `TEST_DATABASE_URL` no está configurada. GitHub Actions está preparado para ejecutarlas sobre PostgreSQL 16, incluyendo dos ventas simultáneas que no deben superar el stock. No se verificó una ejecución de ese workflow en tu repositorio remoto.

La interfaz de Streamlit se revisó en Chromium 131, con Playwright, a 1440 × 1000 y 390 × 844 píxeles. Se inspeccionaron Inicio, catálogo, ficha, carrito lateral, caja, confirmación y BI; se comprobó el recorrido completo de ficha → agregar → aumentar cantidad en el drawer → elegir Yape → confirmar venta → BI. En móvil se probaron navegación, catálogo a dos columnas, drawer y apertura de caja, sin desbordamiento horizontal. Los ocho módulos también se construyeron sin errores mediante AppTest. Las pruebas no sustituyen la revisión del servicio publicado ni de los navegadores reales del personal.

La página Firebase no cambió con esta actualización; su carga y Analytics requieren verificación en el Hosting de prueba.

## Datos de ejemplo

Los datos sintéticos permiten recorrer pantallas y comprobar cálculos; no acreditan uso, compras, ingresos, disminución de quiebres ni precisión del negocio real. El modo demo se identifica en una banda visible y nunca escribe en Supabase. Las operaciones reales requieren `APP_MODE = "cloud"` y acceso autorizado.

## Guion de prueba con el propietario

| Tarea | Evidencia que conviene anotar | Resultado esperado del sistema |
|---|---|---|
| Encontrar ventas de hoy | Tiempo y si requirió ayuda | Inicio muestra fecha Lima, ventas y alertas |
| Registrar cinco artículos | Tiempo, correcciones y ticket | Una venta, varias líneas y stock disminuido |
| Buscar un artículo agotado | Tiempo y comprensión del mensaje | Producto en alerta con stock cero |
| Registrar entrada de proveedor | Documento de compra, unidades y costo | Stock aumenta y queda un movimiento |
| Conciliar un conteo | Stock anterior, físico y motivo | Ajuste registra diferencia y saldo contado |
| Revisar una compra sugerida | Cantidad, explicación, aceptación/descarte y motivo | Decisión persistida sin cambiar stock |
| Interpretar tres KPI | Respuesta del usuario | Distingue ventas, margen y existencia actual |
| Cargar un CSV histórico | Filas, tickets y stock antes/después | Ventas importadas sin descontar stock actual |
| Evaluar pronóstico | Período completo, faltantes, WAPE y comparación | Método simple si IA no lo supera |

El informe plantea un piloto y entrevistas adicionales. Estas mediciones aún no existen en esta entrega. Antes de usar el sistema diariamente, concilia varias ventas y entradas de prueba contra el conteo físico y verifica el acceso por rol en las cuentas reales.

## Pendientes de despliegue

1. Subir esta actualización al repositorio existente y comprobar su recarga en Streamlit.
2. Ejecutar `03_catalogo_visual.sql` en la base elegida y verificar Data API/permisos.
3. Si se utiliza demo, completar la configuración cloud antes de operar con datos reales.
4. Probar operaciones autenticadas contra Supabase en un entorno de prueba.
5. Revisar Firebase Hosting y Analytics si se habilitan como página de entrada.
6. Cargar catálogo y conteo reales, evitando mezclar datos sintéticos.

El informe académico original, el repositorio original, el Supabase actual y el Hosting actual no se modificaron remotamente.
