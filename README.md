# Bodega Marga BI · Tienda inteligente

Adaptación del proyecto Smart Campus para el MVP definido en **G9_INFORME.docx (4).pdf**: registrar ventas por producto, controlar inventario y convertir los registros en decisiones de reposición. Caso piloto: Bodega Marga, Los Olivos, Lima, 2026.

La aplicación principal está en **`app.py`**. Funciona con Python y Streamlit; Supabase guarda la información y Firebase Authentication controla el acceso. Firebase Hosting sirve la página de entrada. No se necesitan PHP, MySQL local, un archivo de reporte de escritorio ni un túnel temporal de Colab.

## Qué incluye

- Interfaz inspirada en las capturas Wix: menú superior, catálogo ilustrado con filtros, ficha de producto, carrito lateral y caja interna.
- Resumen BI con filtros de fechas, categoría y origen; ventas, tickets, margen bruto, tendencias y stock bajo.
- Venta con carrito, búsqueda por código o nombre, descuento por línea y medio de pago.
- Catálogo, entradas, costo promedio ponderado, ajustes por conteo y mermas.
- Anulación completa de ventas con trazabilidad y devolución de stock para operaciones POS.
- Inicio con ventas del día y accesos rápidos; lista de reposición explicada y decisiones con motivo.
- CSV histórico → validación → staging persistente → hechos de ventas → BI.
- Pronóstico por producto: promedio móvil, referencia semanal y Random Forest; comparación temporal de 28 días.
- Roles administrador, cajero y analista; exportaciones CSV; eventos de uso sin datos de clientes.
- Pruebas y configuración de GitHub Actions con PostgreSQL 16.

## Empezar en la nube

Lee **[docs/01_DESPLIEGUE_NUBE.md](docs/01_DESPLIEGUE_NUBE.md)**. Todo puede hacerse desde el navegador: GitHub, Supabase SQL Editor, Streamlit Community Cloud y Cloud Shell de Google para Firebase Hosting.

1. Crea un repositorio nuevo, por ejemplo `bodega-marga-bi`, y sube el contenido de esta carpeta a su raíz.
2. Ejecuta **`database/01_bodega_schema.sql`** en Supabase.
   Después ejecuta **`database/03_catalogo_visual.sql`** para guardar descripción, marca, presentación y foto del producto.
3. Habilita Email/Password en Firebase Authentication y crea las cuentas del personal.
4. Despliega `app.py` en Streamlit Community Cloud con Python 3.12.
5. Completa Settings → Secrets usando `.streamlit/secrets.toml.example`; utiliza `APP_MODE = "cloud"`.
6. Copia la nueva URL de Streamlit en `hosting/config.js` y despliega Hosting.
7. Crea el catálogo, registra el conteo inicial y haz una venta de prueba.

**Si tu proyecto ya está funcionando**, sigue [ACTUALIZAR_DISENO_TIENDA.md](ACTUALIZAR_DISENO_TIENDA.md). La actualización visual se sube al mismo repositorio y conserva su configuración. Solo añade el SQL `03_catalogo_visual.sql`; no requiere volver a cargar el catálogo demo.

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

## Verificación de desarrollo

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

Las pruebas con base PostgreSQL real requieren `TEST_DATABASE_URL` apuntando a una base desechable. La suite limpia únicamente sus tablas `bodega_*`; nunca apuntes esta variable a producción. GitHub Actions crea una instancia de prueba y ejecuta también ventas simultáneas.

La operación comercial conserva todos los datos en Supabase. Los cálculos se ejecutan en el servidor Streamlit y los pronósticos se guardan en Supabase cuando el usuario confirma. Una laptop no necesita permanecer encendida para sostener el despliegue; la disponibilidad depende de los servicios y sus planes.
