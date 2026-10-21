# Validación de la entrega

## Verificación ejecutada

Se revisaron las once capturas nuevas y se ejecutaron pruebas sobre la versión con galería y BI por páginas: **46 pruebas correctas, 6 pruebas de PostgreSQL real omitidas por falta de TEST_DATABASE_URL y 26 comprobaciones SQL sobre PostgreSQL embebido correctas**. El proyecto se probó en demostración con datos sintéticos; no se conectó a los servicios del propietario durante estas pruebas.

- Suite Python y Streamlit AppTest: pruebas de navegación, venta desde la interfaz, evaluación/guardado de pronósticos, decisión de reposición, acceso cloud sin fallback, validación CSV, stock, reintentos, exportación segura y permisos de rol.
- SQL ejecutado sobre PostgreSQL embebido mediante PGlite: migración completa reejecutada, catálogo opcional, ventas con `service_role`, reintentos, UUID con payload diferente, rollback de carrito, anulación, carga histórica y duplicados, costo promedio, merma inválida, decisión de reposición, guardado de pronósticos y denegación a `anon`.
- Compilación de módulos Python y revisión sintáctica de JavaScript y scripts SQL.
- Carrito: agregación de un mismo producto, descuentos y totales, límites de stock, cantidades inválidas y retiro de artículos; filtros y ordenamiento del catálogo.
- AppTest: venta con cantidad modificada y Yape; respuesta incierta después de registrar una venta y reintento con el mismo identificador, sin segundo descuento de stock.
- SQL visual: migración adicional ejecutada dos veces, persistencia de descripción y foto sin cambiar stock ni precios históricos, rechazo completo de una foto con URL inválida y denegación de la nueva función a `anon`.
- BI: seis páginas, operaciones OLAP, tablas del almacén, filtros conservados al pasar por Predicciones y limpieza de filtros; comportamiento con ventas vacías.
- Agregaciones: ticket único en varias categorías, porcentajes ponderados, máscaras del cubo, matriz con una categoría llamada TOTAL, filtros cruzados y horas históricas desconocidas.
- Galería: añadir una casilla conserva campos sin guardar; URL deduplicadas y ordenadas, foto previa conservada al migrar y rechazo transaccional de URL inválidas.
- Pronóstico: portafolio de dos artículos, 28 días de validación por producto, guardado sin duplicados, WAPE ponderado y escenario de stock que excluye fechas pasadas.
- Uso: el embudo cuenta pasos en orden una vez por sesión y excluye eventos sin sesión medida.

PGlite ejecuta las funciones PL/pgSQL y las transacciones con un motor PostgreSQL embebido; no equivale a probar el servicio Supabase remoto, su Data API o varias conexiones concurrentes. Las seis pruebas con PostgreSQL real están incluidas y se omiten localmente cuando `TEST_DATABASE_URL` no está configurada. GitHub Actions está preparado para ejecutarlas sobre PostgreSQL 16, incluyendo dos ventas simultáneas que no deben superar el stock. No se verificó una ejecución de ese workflow en tu repositorio remoto.

La interfaz de Streamlit se revisó en Chromium 131, con Playwright, a 1440 × 1000 y 390 × 844 píxeles. Se inspeccionaron Inicio, catálogo, ficha, carrito lateral, caja, confirmación y BI; se comprobó el recorrido completo de ficha → agregar → aumentar cantidad en el drawer → elegir Yape → confirmar venta → BI. En móvil se probaron navegación, catálogo a dos columnas, drawer y apertura de caja, sin desbordamiento horizontal. Los ocho módulos también se construyeron sin errores mediante AppTest. Las pruebas no sustituyen la revisión del servicio publicado ni de los navegadores reales del personal.

La ampliación completó además **22 comprobaciones de navegador**: editor de dos URL, segunda imagen visible al hover, selección Foto 2, venta con Yape, seis páginas BI, embudo con un recorrido observado, las seis operaciones OLAP, evaluación y consulta de pronósticos guardados y navegación móvil por Resumen/OLAP/Predicciones/Datos. No hubo excepciones JavaScript ni desbordamiento horizontal en esas comprobaciones. Las imágenes externas de la prueba se sirvieron mediante rutas HTTPS interceptadas localmente; esto verifica el mecanismo de galería, no la disponibilidad de un proveedor externo concreto.

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
2. Ejecutar `04_galeria_y_bi.sql` después del esquema base y del `03`, y verificar Data API/permisos.
3. Si se utiliza demo, completar la configuración cloud antes de operar con datos reales.
4. Probar operaciones autenticadas contra Supabase en un entorno de prueba.
5. Revisar Firebase Hosting y Analytics si se habilitan como página de entrada.
6. Cargar catálogo y conteo reales, evitando mezclar datos sintéticos.

Esta actualización no se publicó en tu GitHub ni ejecutó SQL o despliegues en tus cuentas. Las pruebas se realizaron sobre la copia de desarrollo.
