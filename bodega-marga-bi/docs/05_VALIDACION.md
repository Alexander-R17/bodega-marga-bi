# Validación de la entrega

## Verificación ejecutada

Se revisó el material adjunto y se ejecutaron pruebas sobre los archivos finales: **19 pruebas correctas, 4 pruebas de PostgreSQL real pendientes de ejecutar en CI y 14 comprobaciones SQL sobre PostgreSQL embebido correctas**. El proyecto funciona en demostración con datos sintéticos; no se conectó a los servicios del propietario durante estas pruebas.

- Suite Python y Streamlit AppTest: pruebas de navegación, venta desde la interfaz, evaluación/guardado de pronósticos, decisión de reposición, acceso cloud sin fallback, validación CSV, stock, reintentos, exportación segura y permisos de rol.
- SQL ejecutado sobre PostgreSQL embebido mediante PGlite: migración completa reejecutada, catálogo opcional, ventas con `service_role`, reintentos, UUID con payload diferente, rollback de carrito, anulación, carga histórica y duplicados, costo promedio, merma inválida, decisión de reposición, guardado de pronósticos y denegación a `anon`.
- Compilación de módulos Python y revisión sintáctica de JavaScript y scripts SQL.

PGlite ejecuta las funciones PL/pgSQL y las transacciones con un motor PostgreSQL embebido; no equivale a probar el servicio Supabase remoto, su Data API o varias conexiones concurrentes. Las cuatro pruebas con PostgreSQL real están incluidas y se omiten localmente cuando `TEST_DATABASE_URL` no está configurada. GitHub Actions está preparado para ejecutarlas sobre PostgreSQL 16, incluyendo dos ventas simultáneas que no deben superar el stock. Ese workflow no se ha ejecutado en tu repositorio, que todavía no se publicó.

No se ha verificado visualmente la aplicación en un navegador completo en este entorno. Se comprobó la construcción de sus pantallas e interacciones con AppTest. La página Firebase pasó revisión de código y sintaxis; su carga y Analytics requieren verificación en el Hosting de prueba.

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

1. Crear y cargar el repositorio nuevo.
2. Ejecutar la migración en la base elegida y verificar Data API/permisos.
3. Configurar Firebase Authentication, cuentas verificadas y Secrets.
4. Publicar Streamlit y probar operaciones reales en un entorno de prueba.
5. Pegar la URL en `hosting/config.js` y revisar Firebase en canal de vista previa.
6. Confirmar conexión de Analytics tras aceptar medición.
7. Cargar catálogo y conteo reales, evitando mezclar datos sintéticos.

El informe académico original, el repositorio original, el Supabase actual y el Hosting actual no se modificaron remotamente.
