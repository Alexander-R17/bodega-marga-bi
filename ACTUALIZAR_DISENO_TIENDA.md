# Actualizar Bodega Marga con el diseño de tienda

Esta versión adapta el estilo de las capturas Wix a la aplicación existente de Streamlit. Conserva Bodega Marga, los productos de abarrotes y los ocho módulos de operación y BI. La entrega contiene los archivos actualizados; todavía debes subirlos a tu repositorio para que aparezcan en tu aplicación publicada.

## Qué cambia

- Menú superior con Inicio, Tienda interna, Inventario, BI, Reposición, Pronóstico, Importar y Actividad.
- Inicio con tonos durazno y menta, accesos a ventas y BI, indicadores reales de la sesión y alertas de existencias.
- Catálogo con imágenes, categorías, rango de precios, búsqueda por nombre o código, ordenamiento y disponibilidad.
- Ficha con imagen, precio, cantidad e información del producto: descripción, categoría, proveedor, marca y presentación cuando existan.
- Carrito lateral para revisar artículos y cambiar cantidades; carrito completo con descuento por línea y resumen de la venta.
- Selección entre Efectivo, Yape, Plin, Tarjeta y Transferencia antes de confirmar.

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
| `assets/` completa | CSS, ilustración de la tienda e imágenes de los productos |
| `data/productos_demo.csv` | Descripciones y presentaciones de la demostración |
| `.streamlit/config.toml` | Colores base del nuevo diseño |
| `database/03_catalogo_visual.sql` | Migración adicional para Supabase |
| `tests/` y `.github/workflows/tests.yml` | Verificaciones de aplicación y PostgreSQL |

5. Guarda con **Commit changes** en la rama que usa tu app, normalmente `main`. La carpeta `.streamlit` puede no mostrarse en algunos exploradores; verifica su archivo en GitHub. Conserva tus Secrets en Streamlit.

## 2. Añadir la ficha visual en Supabase

Si usas `APP_MODE = "demo"`, puedes ver el diseño inmediatamente; la demostración no requiere ejecutar SQL ni utiliza Supabase.

Para guardar fichas en modo nube:

1. Abre tu proyecto de Supabase → **SQL Editor → New query**.
2. Copia completo `database/03_catalogo_visual.sql` y pulsa **Run**.
3. Este SQL presupone que ya ejecutaste `01_bodega_schema.sql`. Añade cuatro campos de producto y una función privada para guardarlos. Se puede volver a ejecutar; conserva el stock, las ventas y el historial.
4. No necesitas volver a ejecutar el catálogo opcional ni importar nuevamente las ventas de ejemplo.

La lectura del catálogo y las ventas siguen siendo compatibles con la base anterior. El formulario de guardar producto necesita la nueva función; si falta, la app indica que ejecutes `03_catalogo_visual.sql`.

## 3. Revisar la aplicación en Streamlit

1. Abre tu aplicación publicada: `https://bodega-marga-bi.streamlit.app`.
2. Espera a que termine la actualización del repositorio. Si continúa el diseño anterior, entra a **Manage app → Reboot app** y recarga la página.
3. Si el registro muestra una versión antigua de Streamlit, confirma que se subió el nuevo `requirements.txt` y vuelve a reiniciar.
4. Prueba: **Tienda interna → Ver producto → Agregar al carrito → Carrito → Ver carrito y finalizar → elegir pago → Confirmar venta**.
5. Revisa que disminuya el stock y que la venta aparezca en BI y Actividad. En demo, estos cambios solo duran durante esa sesión.

La configuración actual de Firebase Authentication y los Secrets de Supabase se conserva. Esta actualización del dashboard no requiere volver a desplegar Firebase Hosting. Para activar operaciones persistentes, sigue la configuración `APP_MODE = "cloud"` de `docs/01_DESPLIEGUE_NUBE.md`.

## 4. Colocar fotos y textos propios

Como administrador entra a **Inventario → Catálogo**, selecciona un producto y completa Descripción, Marca, Presentación y URL HTTPS de la foto. Guarda el producto y abre su ficha en la tienda.

Las imágenes incluidas son ilustraciones originales de ejemplo, no fotografías de marcas comerciales. Una URL HTTPS de imagen sustituye la ilustración del artículo; debe ser accesible para el navegador del usuario. Un producto nuevo sin foto utiliza una ilustración genérica. La información visual nunca modifica las existencias: las entradas, ajustes y ventas siguen siendo sus operaciones propias.

## Funciones conservadas

Los filtros y exportaciones BI, inventario y movimientos, anulación completa, sugerencias de reposición con motivos, evaluación y guardado de pronósticos, importación histórica y actividad siguen disponibles. Se mantienen los roles administrador/cajero/analista, la autenticación Firebase y las operaciones atómicas de Supabase con identificadores de reintento.

La validación ejecutada y sus límites están documentados en `docs/05_VALIDACION.md`.
