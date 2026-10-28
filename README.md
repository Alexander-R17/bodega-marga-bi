# Actualización 14 · app Android nativa

Lee [LEEME_APP_NATIVA_14.txt](LEEME_APP_NATIVA_14.txt). Esta versión sustituye la 13: interfaz nativa, Firebase existente, inventario y carrito compartidos. Sobre la instalación operativa ejecuta **solo SQL 14** y publica `tienda-movil`.

# Bodega Marga BI · Tienda inteligente

Adaptación del proyecto Smart Campus para el MVP definido en **G9_INFORME.docx (4).pdf**: registrar ventas por producto, controlar inventario y convertir los registros en decisiones de reposición. Caso piloto: Bodega Marga, Los Olivos, Lima, 2026.

La aplicación principal está en **`app.py`**. Funciona con Python y Streamlit; Supabase guarda la información y Firebase Authentication controla el acceso. Firebase Hosting sirve la página de entrada. No se necesitan PHP, MySQL local, un archivo de reporte de escritorio ni un túnel temporal de Colab.

## Qué incluye

- Interfaz inspirada en las capturas Wix: menú superior, catálogo ilustrado con filtros, ficha de producto, carrito lateral y caja interna.
- BI en siete páginas: resumen, ventas/rentabilidad, diagnóstico/inventario, cubo OLAP, predicciones, almacén/uso y fiados/cobranza.
- OLAP con Slice, Dice, Drill-down, Roll-up, Pivot y cubo con subtotales; filtros de fechas, año, mes, producto, categoría, proveedor, pago y origen.
- Galería de hasta ocho URL por producto, cambio de imagen al pasar el cursor y selección de fotos en la ficha.
- Venta con carrito, búsqueda por código o nombre, descuento por línea y medio de pago.
- Catálogo, entradas, costo promedio ponderado, ajustes por conteo y mermas.
- Anulación completa de ventas con trazabilidad y devolución de stock para operaciones POS.
- Inicio con ventas del día y accesos rápidos; lista de reposición explicada y decisiones con motivo.
- CSV histórico → validación → staging persistente → hechos de ventas → BI.
- Pronóstico de 1 a 20 productos: promedio móvil, referencia semanal y Random Forest; validación temporal de 28 días, ingresos orientativos y escenario de existencias.
- Roles administrador, cajero y analista; exportaciones CSV; eventos de uso sin datos de clientes.
- Pruebas y configuración de GitHub Actions con PostgreSQL 16.

## Empezar en la nube

Lee **[docs/01_DESPLIEGUE_NUBE.md](docs/01_DESPLIEGUE_NUBE.md)**. Todo puede hacerse desde el navegador: GitHub, Supabase SQL Editor, Streamlit Community Cloud y Cloud Shell de Google para Firebase Hosting.

1. Crea un repositorio nuevo, por ejemplo `bodega-marga-bi`, y sube el contenido de esta carpeta a su raíz.
2. Ejecuta **`database/01_bodega_schema.sql`** en Supabase.
   Después ejecuta **`database/03_catalogo_visual.sql`** para guardar descripción, marca, presentación y foto del producto.
   Luego ejecuta **`database/04_galeria_y_bi.sql`** para la galería, el cubo SQL y los eventos por sesión.
   Finalmente ejecuta **`database/05_confirmacion_pago.sql`** para la confirmación manual del pago en caja.
3. Habilita Email/Password en Firebase Authentication y crea las cuentas del personal.
4. Despliega `app.py` en Streamlit Community Cloud con Python 3.12.
5. Completa Settings → Secrets usando `.streamlit/secrets.toml.example`; utiliza `APP_MODE = "cloud"`.
6. Copia la nueva URL de Streamlit en `hosting/config.js` y despliega Hosting.
7. Crea el catálogo, registra el conteo inicial y haz una venta de prueba.

**Si tu proyecto ya está funcionando con la ficha visual**, sigue [ACTUALIZAR_DISENO_TIENDA.md](ACTUALIZAR_DISENO_TIENDA.md). Añade `04_galeria_y_bi.sql` y sube el código al mismo repositorio. No vuelvas a cargar los datos demo sobre el negocio real.

**Nombres del equipo, cobro y vista limpia:** sigue [docs/08_NOMBRES_PAGO_INTERFAZ.md](docs/08_NOMBRES_PAGO_INTERFAZ.md). Si ya aplicaste las migraciones anteriores, ejecuta solamente `05_confirmacion_pago.sql` y actualiza los archivos de esta entrega.

## Demostración

Sin configuración la app abre en modo **demo**, con datos sintéticos y cambios solo en memoria de esa sesión. Para una demostración publicada puedes poner `APP_MODE = "demo"` en Secrets. No se conecta a Supabase ni acepta credenciales reales. Para operar el negocio configura explícitamente `APP_MODE = "cloud"`: si falla una conexión, ese modo muestra el error y nunca sustituye los datos reales por una demo.

Los 12 productos y 1031 líneas de `data/ventas_demo.csv`, entre el 1 de julio y el 13 de octubre de 2026, son ficticios. No representan ventas observadas, stock físico ni resultados de Bodega Marga. Para probar el modo nube usa una base de pruebas, ejecuta el catálogo opcional y luego importa ese CSV.

## Alcance del MVP

No emite comprobantes electrónicos ni calcula impuestos; no ofrece pagos en línea, tienda pública, programa de puntos, recomendaciones personales, voz o devoluciones parciales. Las alertas se calculan al consultar el tablero: no envía notificaciones programadas. La lectura por código admite un escáner que actúe como teclado; no incluye reconocimiento por cámara.

El modelo cubre **una bodega**. La expansión SaaS a varias bodegas exige aislamiento por organización, permisos por tienda, facturación de suscripciones y pruebas adicionales. El precio S/ 89, VAN y TIR del informe son supuestos del negocio del software; no son los KPI de ventas de la tienda y no se mezclan en el tablero.

## Documentación

- [Despliegue y configuración](docs/01_DESPLIEGUE_NUBE.md)
- [Alcance, cambios y correspondencia con tu informe](docs/02_ALCANCE_Y_CAMBIOS.md)
- [Arquitectura, modelo de datos y KPI](docs/03_MODELO_Y_KPIS.md)
- [Referencias académicas y técnicas](docs/04_REFERENCIAS.md)
- [Validación y recorrido de prueba](docs/05_VALIDACION.md)
- [Actualizar la interfaz existente](ACTUALIZAR_DISENO_TIENDA.md)
- [Páginas BI, cubos y galería](docs/06_BI_Y_GALERIA.md)

## Verificación de desarrollo

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

Las pruebas con base PostgreSQL real requieren `TEST_DATABASE_URL` apuntando a una base desechable. La suite limpia únicamente sus tablas `bodega_*`; nunca apuntes esta variable a producción. GitHub Actions crea una instancia de prueba y ejecuta también ventas simultáneas.

La operación comercial conserva todos los datos en Supabase. Los cálculos se ejecutan en el servidor Streamlit y los pronósticos se guardan en Supabase cuando el usuario confirma. Una laptop no necesita permanecer encendida para sostener el despliegue; la disponibilidad depende de los servicios y sus planes.
## Actualización de caja e historial

La migración `database/06_clientes_historial_ticket.sql` añade clientes identificados, referencias de pago, tickets internos inmutables y búsqueda paginada. La aplicación reduce consultas repetidas y verifica Firebase una vez por ejecución. Consulta [la guía de instalación y alcance](docs/10_RENDIMIENTO_CLIENTES_Y_TICKETS.md). Los medios manuales conservan la confirmación en caja; el flujo Yape actualizado se describe en la guía 15. El ticket PDF no sustituye una boleta electrónica SUNAT.

# Actualización: fiados y espera de Yape

Consulta [instalación y alcance](docs/12_FIADOS_Y_ESPERA_DE_PAGO.md) y
[propuesta de migración a web propia](docs/13_MIGRACION_WEB_Y_ALOJAMIENTO.md).
Las migraciones 06 a 09 añaden clientes, tickets, avisos, cuentas por cobrar y órdenes de cobro.
Activa `CREDIT_ENABLED = true` para fiados; la espera requiere además configurar el lector Android.
La actualización SQL 10 conecta el botón principal de Yape con la espera y el registro basado en avisos. Consulta [la guía vigente de caja, clientes y error 401](docs/15_CAJA_YAPE_CLIENTES.md). Requiere instalar y conectar el lector Android; no verifica saldo bancario. Fiado permite seleccionar las cuentas existentes.

