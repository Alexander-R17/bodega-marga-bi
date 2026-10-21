# Galería, análisis BI y cubos de Bodega Marga

## Organización del BI

La navegación superior de la tienda conserva sus ocho módulos. Dentro de **BI** hay seis páginas, con indicador de posición y botones Anterior/Siguiente. Cada una renderiza su contenido al seleccionarla; los gráficos se distribuyen en pares y las tablas tienen exportación CSV.

| Página | Preguntas que responde | Gráficos y tablas |
|---|---|---|
| 1. Resumen ejecutivo | ¿Qué se vendió, qué concentra el resultado y qué conviene revisar? | Ventas, unidades, tickets y margen; cuatro tarjetas descriptiva/diagnóstica/predictiva/prescriptiva; evolución, participación por categoría y prioridades de stock |
| 2. Ventas y rentabilidad | ¿Cómo evolucionan ventas/margen y qué productos, pagos y días aportan más? | Tendencia día/mes/trimestre/año; ranking; participación por pago; unidades por día de semana; tablas por producto, categoría, proveedor, ticket o línea |
| 3. Diagnóstico e inventario | ¿Qué artículos concentran las ventas y cuáles tienen existencias críticas? | Pareto y ABC; dispersión volumen/margen; estados por categoría; stock frente al mínimo; cobertura, velocidad, valor y compra sugerida |
| 4. Cubo OLAP | ¿Cómo cambia una medida al cruzar o agregar dimensiones? | Matriz, mapa de calor, Slice, Dice, Drill-down, Roll-up, Pivot, cubo completo de hasta tres dimensiones y subtotales; matriz día/hora si existen horas POS |
| 5. Predicciones | ¿Qué unidades se proyectan y qué implicarían para ingreso y existencias? | Uno a veinte productos, proyección diaria, ranking futuro, saldo sin entradas, ingreso orientativo, validación temporal, comparación de métodos, tablas y consulta de cortes guardados |
| 6. Datos y uso | ¿De dónde vienen los datos y qué actividad se ha medido? | Hechos/dimensiones/cubo SQL; calidad; lotes y origen; cuentas técnicas con eventos, sesiones, embudo ordenado y tipos de eventos |

Las capturas de Smart Campus se usaron como referencia de organización analítica. Los indicadores energéticos no se convirtieron en ventas ni se copiaron como métricas del negocio. La estética sigue siendo la interfaz de tienda ya acordada.

## Filtros y alcance

Resumen, Ventas, Diagnóstico y OLAP comparten período, años, meses, categorías, productos, proveedores, medios de pago y origen POS/HISTORICO. Las selecciones se intersectan; una selección vacía de una dimensión significa todos sus valores. **Limpiar filtros** restaura el período predeterminado y elimina las selecciones.

- Los filtros de fechas operan sobre la fecha comercial de la venta.
- En inventario, producto/categoría/proveedor limitan los artículos. Stock, costo y mínimo son actuales; la velocidad usa las ventas de los últimos 28 días hasta hoy en Lima. Elegir otro mes comercial no reconstruye existencias pasadas.
- Predicciones tiene su propio período de entrenamiento y lista de productos; no hereda un filtro comercial de 28 días que dejaría al modelo sin los 84 días mínimos.
- El almacén muestra hechos comerciales filtrados; dimensiones, cubo mensual SQL y controles de calidad consultan el almacén completo. La página lo indica.
- Uso tiene su propio filtro de fechas de eventos. No se recorta por categoría o medio de pago, porque esos campos no describen un evento de navegación.

## Cómo utilizar las operaciones OLAP

| Operación | Ejemplo en la bodega | Resultado |
|---|---|---|
| Pivot | Filas Categoría, columnas Mes, medida Ventas S/ | Matriz y mapa de calor; opción de intercambiar ejes |
| Slice | Fijar Medio de pago = Yape | Sección del cubo con las ventas de ese pago |
| Dice | Categoría en Abarrotes/Bebidas y Pago en Yape/Efectivo | Intersección de ambos subconjuntos |
| Drill-down | Elegir Lácteos y abrir sus productos | Mayor detalle de una categoría |
| Drill-down temporal | Año → trimestre → mes → día | Descenso progresivo de la jerarquía de fechas |
| Roll-up | Subir las líneas al nivel Mes o Categoría | Agregación por un nivel superior |
| Cubo y subtotales | Mes × Categoría × Pago | Todas las combinaciones de dimensiones y sus niveles TOTAL |

Las medidas disponibles son ventas, unidades, margen bruto, tickets únicos, ticket promedio y margen bruto %. El total de tickets se calcula con `COUNT DISTINCT`, incluso cuando el mismo ticket aparece en varias categorías. Los porcentajes y promedios se recalculan con los hechos de cada celda/subtotal: no se suman ni se promedian sin ponderación.

La matriz presenta un total recalculado por fila, por columna y general. El cubo completo incluye una máscara de agrupación para distinguir sus niveles: **no sumes filas de máscaras distintas**, porque repetirías los mismos hechos. Si una categoría se llama TOTAL, la matriz utiliza una etiqueta total alternativa para conservar ese valor real.

## Cubo y modelo de datos

El grano sigue siendo una línea por producto y ticket completado. Las tablas ya existentes cubren productos, categorías, proveedores, tiempo, cabeceras y detalle de venta; no se crean copias de esas tablas para decorar el dashboard.

`04_galeria_y_bi.sql` añade `bodega_v_cubo_ventas`, una vista virtual con `GROUP BY CUBE` sobre mes, categoría y medio de pago, con las medidas y subtotales correspondientes. La vista tiene `security_invoker` y acceso exclusivo de `service_role`, igual que los hechos privados. No es un cubo SSAS ni un servicio externo adicional.

La página OLAP interactiva agrega los hechos cargados en Streamlit para permitir todas las dimensiones y filtros de la bodega. La vista SQL ofrece el cubo mensual estándar desde PostgreSQL y se puede consultar en Datos y uso → Almacén de datos. No materializa una segunda historia de ventas.

Las categorías y proveedores reflejan la clasificación actual del catálogo. Los precios y costos del detalle de una venta sí son históricos. No se añadió historial SCD2 de reclasificaciones ni inventario reconstruido a una fecha anterior.

## Proyecciones y sus cuatro vistas

1. Selecciona de uno a veinte productos y un registro completo de al menos 84 días. Confirma que un día sin líneas significa cero ventas; si hubo faltantes o registros omitidos, delimita/corrige el período antes de evaluar.
2. El sistema reserva los últimos 28 días y entrena con los anteriores. Compara promedio móvil de 28 días, referencia estacional semanal y Random Forest, sin introducir valores observados del futuro en sus rezagos.
3. Cada artículo elige Random Forest solo si supera al mejor método sencillo. El empate conserva la referencia. Luego proyecta 7, 14 o 28 días posteriores al corte.
4. Se muestran cuatro vistas: unidades futuras, ranking por producto, saldo teórico sin entradas e importe orientativo por día. Estas vistas derivan del pronóstico de unidades; no son cuatro modelos independientes.
5. La tabla de métodos incluye WAPE por producto y método. El WAPE del portafolio suma errores absolutos de los productos y los divide entre la suma de unidades observadas, ponderando por volumen.
6. **Guardar evaluación y pronóstico** persiste unidades, corte, método y WAPE. Al consultar resultados guardados se elige el último corte por producto o un corte específico, evitando sumar varias versiones superpuestas.

El ingreso orientativo multiplica unidades por precio actual; no incorpora descuentos futuros ni constituye una predicción monetaria entrenada por separado. El saldo parte del stock actual y solo descuenta días posteriores a hoy. Los saldos negativos representan unidades que no se cubrirían en el escenario, no existencias físicas negativas ni probabilidades de quiebre. Si el horizonte ya terminó, no se presenta como una proyección futura de stock.

La compra de escenario cubre las unidades previstas del horizonte restante y el mínimo actual; no considera pedidos pendientes. La decisión de compra sigue requiriendo revisión. La validación usada para seleccionar el método es preliminar; no es una prueba final independiente ni un intervalo de confianza.

## Analítica interna medida

La actualización añade sesión y página a `bodega_eventos`. Registra aperturas del catálogo, adición al carrito, apertura de caja, confirmación de venta y navegación por páginas BI. La sesión corresponde a una sesión de Streamlit; una recarga o una nueva sesión puede generar otro identificador.

El embudo cuenta sesiones con los pasos en orden: catálogo → agregar → caja → confirmar. Cada sesión cuenta una vez por etapa. La conversión observada divide las sesiones que completaron ese recorrido entre las que abrieron catálogo en el período. No mide abandono definitivo, compradores únicos ni sesiones de Google Analytics. No se recopilan dispositivo, IP, datos de tarjeta ni datos del cliente. Los eventos anteriores sin sesión no se incluyen artificialmente en el embudo.

## Galería de URL

El catálogo conserva `imagen_url` como portada compatible y añade `imagenes_urls` con hasta ocho URL HTTPS. El botón Agregar otra URL conserva los campos escritos; los enlaces vacíos se omiten y los duplicados se eliminan sin cambiar el orden. La migración conserva una foto anterior como primera imagen.

En las tarjetas la galería alterna cada 1,6 segundos mientras el cursor permanece encima. En la ficha se elige Foto 1/Foto 2, también en dispositivos táctiles. Si el navegador solicita movimiento reducido, la animación se desactiva y queda disponible la selección manual. Sin URL se utiliza la ilustración local del producto.

Solo se guardan direcciones, no bytes PNG/JPG ni archivos en Supabase Storage. La carga la realiza el navegador directamente desde el alojamiento de cada imagen; el enlace debe seguir siendo público, directo y accesible. Se rechazan URL sin HTTPS, con espacios o credenciales incrustadas.

## Referencias técnicas

- [PostgreSQL 16: GROUPING SETS, CUBE y ROLLUP](https://www.postgresql.org/docs/16/queries-table-expressions.html#QUERIES-GROUPING-SETS)
- [Plotly: mapas de calor y matrices](https://plotly.com/python/heatmaps/)
- [Streamlit: estado de sesión](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state)

La verificación de esta entrega se encuentra en `05_VALIDACION.md`.
