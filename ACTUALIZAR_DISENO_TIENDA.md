# Actualizar Bodega Marga: galería y BI por páginas

Esta versión adapta el estilo de las capturas Wix a la aplicación existente de Streamlit. Conserva Bodega Marga, los productos de abarrotes y los ocho módulos de operación y BI. La entrega contiene los archivos actualizados; todavía debes subirlos a tu repositorio para que aparezcan en tu aplicación publicada.

La ampliación nueva mantiene ese diseño y añade seis páginas BI, operaciones OLAP, proyecciones de varios productos y varias imágenes por URL. Si ya aplicaste `03_catalogo_visual.sql`, el único SQL nuevo es **`04_galeria_y_bi.sql`**.

Para modo nube, aplica primero el SQL del apartado 2 y después publica los archivos en GitHub. Si personalizaste `hosting/config.js`, conserva los valores de tu sitio: las rutas de la tabla siguiente contienen la actualización del dashboard.

## Qué cambia

- Menú superior con Inicio, Tienda interna, Inventario, BI, Reposición, Pronóstico, Importar y Actividad.
- Inicio con tonos durazno y menta, accesos a ventas y BI, indicadores reales de la sesión y alertas de existencias.
- Catálogo con imágenes, categorías, rango de precios, búsqueda por nombre o código, ordenamiento y disponibilidad.
- Ficha con imagen, precio, cantidad e información del producto: descripción, categoría, proveedor, marca y presentación cuando existan.
- Carrito lateral para revisar artículos y cambiar cantidades; carrito completo con descuento por línea y resumen de la venta.
- Selección entre Efectivo, Yape, Plin, Tarjeta y Transferencia antes de confirmar.
- Botón **Agregar otra URL de imagen referencial**, hasta ocho imágenes, cambio al pasar el cursor y selección Foto 1/Foto 2 en la ficha.
- BI con navegación propia: Resumen ejecutivo, Ventas y rentabilidad, Diagnóstico e inventario, Cubo OLAP, Predicciones y Datos y uso.

No hay secciones de contacto, políticas de envío ni políticas de devoluciones. El sistema registra pagos recibidos en caja; no procesa tarjetas, Yape ni Plin mediante una pasarela. La anulación administrativa por error se conserva en Inventario porque corrige el registro interno y mantiene la trazabilidad.

## 1. Subir los archivos al mismo GitHub

1. Descarga `Bodega_Marga_BI.zip` y descomprímelo.
2. Abre tu repositorio actual de Bodega Marga. Puedes conservar el mismo nombre y la misma URL de Streamlit.
3. En **Add file → Upload files**, sube el contenido de la carpeta `bodega-marga-bi`, respetando sus subcarpetas y reemplazando los archivos anteriores. **`app.py` debe quedar en la raíz**, no dentro de una carpeta adicional. No subas solamente el ZIP.
4. Comprueba especialmente estos archivos y carpetas:

| Ruta | Para qué sirve |
|---|---|
| `app.py` | Une las pantallas existentes con la nueva navegación |
| `requirements.txt` | Instala Streamlit 1.66 o superior, necesario para el carrito lateral nativo |
| `bodega/storefront.py` | Inicio, catálogo, ficha de producto, carrito y caja |
| `bodega/cart.py` y `bodega/ui.py` | Validación del carrito, imágenes y presentación |
| `bodega/analytics.py` y `bodega/repository.py` | Compatibilidad con las fichas visuales y su guardado |
| `bodega/media.py` y `bodega/telemetry.py` | Galería por URL y eventos internos medidos |
| `bodega/bi.py` y `bodega/bi_pages.py` | Agregaciones, filtros, cubos y páginas BI |
| `bodega/forecasting.py` y `bodega/prediction_page.py` | Evaluación por producto, escenarios y consulta de pronósticos |
| `assets/` completa | CSS, ilustración de la tienda e imágenes de los productos |
| `data/productos_demo.csv` | Descripciones y presentaciones de la demostración |
| `.streamlit/config.toml` | Colores base del nuevo diseño |
| `database/03_catalogo_visual.sql` | Migración adicional para Supabase |
| `database/04_galeria_y_bi.sql` | Galería, vista de cubo SQL y eventos por sesión |
| `tests/` y `.github/workflows/tests.yml` | Verificaciones de aplicación y PostgreSQL |

5. Guarda con **Commit changes** en la rama que usa tu app, normalmente `main`. La carpeta `.streamlit` puede no mostrarse en algunos exploradores; verifica su archivo en GitHub. Conserva tus Secrets en Streamlit.

## 2. Aplicar el SQL nuevo en Supabase

Si usas `APP_MODE = "demo"`, puedes ver el diseño inmediatamente; la demostración no requiere ejecutar SQL ni utiliza Supabase.

Para guardar fichas en modo nube:

1. Abre tu proyecto de Supabase → **SQL Editor → New query**.
2. Si ya guardabas fotos y descripciones con la versión anterior, ejecuta completo **`database/04_galeria_y_bi.sql`**. La copia independiente entregada se llama `Bodega_Marga_Galeria_BI.sql` y tiene el mismo contenido.
3. Si aún no aplicaste `03_catalogo_visual.sql`, ejecútalo antes del `04`. Ambos presuponen que existe el esquema base `01`.
4. El `04` conserva la imagen anterior como primera URL, añade la lista de imágenes, el cubo relacional virtual y campos de sesión/página en eventos. Se puede volver a ejecutar; no cambia stock ni ventas.
5. No vuelvas a cargar el catálogo opcional ni el historial demo sobre una instalación real.

La lectura del catálogo y las ventas sigue siendo compatible con la base anterior. El nuevo formulario de guardar producto necesita el SQL `04`; si falta, la app lo indica. Los eventos nuevos y el cubo SQL también requieren esa actualización.

## 3. Revisar la aplicación en Streamlit

1. Abre tu aplicación publicada: `https://bodega-marga-bi.streamlit.app`.
2. Espera a que termine la actualización del repositorio. Si continúa el diseño anterior, entra a **Manage app → Reboot app** y recarga la página.
3. Si el registro muestra una versión antigua de Streamlit, confirma que se subió el nuevo `requirements.txt` y vuelve a reiniciar.
4. Prueba: **Tienda interna → Ver producto → Agregar al carrito → Carrito → Ver carrito y finalizar → elegir pago → Confirmar venta**.
5. Revisa que disminuya el stock y que la venta aparezca en BI y Actividad. En demo, estos cambios solo duran durante esa sesión.

Para esta instalación se ha elegido el nuevo proyecto Firebase `bodega-marga-bi`. Actualiza los valores de Firebase y su cuenta de servicio en Secrets de Streamlit con ese mismo proyecto. Conserva los valores de Supabase de tu bodega. La guía [docs/07_ACTIVAR_FIREBASE.md](docs/07_ACTIVAR_FIREBASE.md) explica el paso de demo a modo real. Si publicas la portada, utiliza también la configuración nueva de `hosting/config.js` y el proyecto `bodega-marga-bi` al desplegar Hosting.

## 4. Colocar fotos y textos propios

Como administrador entra a **Inventario → Catálogo**, selecciona un producto y completa Descripción, Marca y Presentación. Escribe la primera URL y pulsa **Agregar otra URL de imagen referencial** para añadir otra casilla. Los campos ya escritos se conservan al añadir casillas. Puedes guardar hasta ocho URL; deja vacía una para omitirla o utiliza **Quitar última URL**. Al terminar pulsa **Guardar producto**.

En la tienda, pasa el cursor por la tarjeta: las imágenes alternan cada 1,6 segundos mientras permanece encima. En la ficha elige **Foto 1**, **Foto 2**, etc.; esta selección también funciona en celular. La primera URL es la portada. Los enlaces repetidos se guardan una sola vez.

Las imágenes incluidas son ilustraciones originales de ejemplo, no fotografías de marcas comerciales. Una URL HTTPS de imagen sustituye la ilustración del artículo; debe ser accesible para el navegador del usuario. Un producto nuevo sin foto utiliza una ilustración genérica. La información visual nunca modifica las existencias: las entradas, ajustes y ventas siguen siendo sus operaciones propias.

Solo se guarda el texto de las URL en Supabase, sin subir archivos al Storage. Las imágenes las sirve su alojamiento externo; su carga depende de que el enlace siga accesible.

## 5. Recorrer el nuevo BI

Abre **BI** y cambia de página con el menú interno o **Anterior/Siguiente**. Solo se renderiza la página elegida. Resumen, Ventas, Diagnóstico y OLAP comparten filtros; Predicciones tiene su período propio para no cortar por accidente el historial de entrenamiento. El almacén, la calidad y el uso indican qué datos globales consultan.

Los gráficos, tablas, filtros y ejemplos de operaciones se describen en [docs/06_BI_Y_GALERIA.md](docs/06_BI_Y_GALERIA.md). Las métricas del período usan ventas completadas; las existencias son actuales. El sistema no reconstruye stock histórico ni inventa horas de ventas importadas.

## Funciones conservadas

Los filtros y exportaciones BI, inventario y movimientos, anulación completa, sugerencias de reposición con motivos, evaluación y guardado de pronósticos, importación histórica y actividad siguen disponibles. Se mantienen los roles administrador/cajero/analista, la autenticación Firebase y las operaciones atómicas de Supabase con identificadores de reintento.

La validación ejecutada y sus límites están documentados en `docs/05_VALIDACION.md`.
