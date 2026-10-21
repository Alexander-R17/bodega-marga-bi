# Adaptación del proyecto y relación con el informe

Fuente de requisitos: **G9_INFORME.docx (4).pdf**, 30 páginas, recibido con el ZIP de Smart Campus. Se revisaron el resumen, objetivos, flujo de pantallas, MVP, pronóstico, validación y anexos, junto con los prototipos de las páginas 6 y 7. Se conservaron la identidad verde de la propuesta y el enfoque de tareas del propietario; la interfaz se implementó con componentes Streamlit.

## Requisitos implementados

| Informe | Implementación | Cómo comprobarla |
|---|---|---|
| Inicio: ventas del día, pendientes y acceso a venta, pp. 6–7 | Página Inicio, fecha de Lima y accesos rápidos | Registrar una venta y consultar stock/ventas del día |
| Venta por producto, pp. 6–7 y 19 | Búsqueda por nombre/código, carrito, cantidades, descuento y pago | Vender varios artículos con un solo ticket |
| Inventario y entradas, pp. 6 y 19 | Catálogo, ENTRADA, AJUSTE y MERMA; kardex | Conciliar stock contra conteo físico |
| Tablero: tendencias, más vendidos y alertas, p. 6 | Resumen BI con filtros, gráficos y detalle descargable | Cambiar fechas y categorías; comparar con las líneas |
| Reposición con explicación y aceptar/descartar, p. 6 | Fórmula explícita y registro persistente de decisión/motivo | Guardar decisión y verla en Actividad y datos |
| Historial e importación, p. 20 | CSV validado, staging y lote procesado atómicamente | Importar y repetir un archivo; detectar duplicados |
| Referencia sencilla antes de IA, pp. 2 y 20 | Promedio de 28 días y referencia semanal | Revisar WAPE de los tres métodos |
| Cuatro semanas posteriores para evaluar, p. 20 | Últimos 28 días como validación; mínimo 56 anteriores para entrenar | Revisar fechas de comparación y fecha de corte |
| Meta exploratoria de 80 %, p. 4 | Muestra índice 100 × (1 − WAPE) sin inventar ni forzar desempeño | Anotar resultado observado del piloto |
| Faltantes ocultan demanda, p. 20 | Declaración de cobertura y bloqueo si se reporta historia incompleta/faltantes | Delimitar un período consistente antes de evaluar |

El prototipo visual de reposición muestra un promedio de 14 días; el texto del MVP no fija ese parámetro. Se eligió **28 días** para el cálculo inicial y se muestra explícitamente en la aplicación. Cambiarlo tras el piloto es una decisión de producto, no una garantía de mejora.

## Cambios respecto a Smart Campus

| Anterior | Nueva versión |
|---|---|
| Edificios y ambientes | Productos, categorías y proveedores |
| Consumo energético y temperatura | Unidades, ventas, costos, descuento y margen bruto |
| Riesgo de sobreconsumo | Stock bajo, agotados y sugerencias de reposición |
| Predicción sobre los mismos registros usados al entrenar | Validación cronológica y pronóstico posterior al corte |
| PHP MVC y endpoints duplicados | Aplicación Python unificada en Streamlit |
| Carpetas y rutas de reportes de escritorio | Gráficos Plotly en Streamlit y exportación CSV |
| MySQL y SQL alternativos del campus | Una migración PostgreSQL nueva, aditiva y con permisos privados |
| Túneles y notebooks como dependencia de ejecución | Cálculo en el servidor Streamlit publicado |
| Login propio y tablas de usuarios heredadas | Firebase Authentication, correo verificado y roles en Secrets |
| Página universitaria | Página de entrada Bodega Marga para Firebase Hosting |

En el nuevo paquete no se incluyen `powerbi/`, archivos `.pbix`, `PowerBIController.php`, integraciones de Looker, bases MySQL ni los datos energéticos. Tampoco se incluye el código PHP antiguo. El ZIP original conserva ese proyecto; no se modificó el repositorio remoto original ni se eliminaron tablas existentes.

## Límites que respeta el informe

El informe deja fuera del primer MVP voz, catálogo público de productos, facturación electrónica, puntos y promociones individualizadas. Esta entrega no los presenta como implementados. La página pública de entrada describe la herramienta, sin publicar precios/stock de la bodega.

La aplicación trabaja en unidades enteras por producto. Si se venden productos por peso, deberán añadirse unidades de medida, cantidades decimales, conversiones y pruebas. Solo se permite anulación completa de un ticket; no hay devolución parcial ni notas tributarias.

Se calcula velocidad de salida y productos sin ventas recientes. No se muestra una rotación contable exacta: ese indicador requiere costo de ventas y existencias promedio comparables en todo el período. Los costos y el margen son orientativos para gestión, no estados financieros.

La regla de reposición no incorpora pedidos en tránsito, estacionalidades especiales o demanda no atendida. Registrar una decisión no genera un pedido al proveedor. La compra sigue bajo revisión del bodeguero y luego se registra la entrada recibida.

## Validación pendiente en Bodega Marga

Las metas de adopción, tiempos de tarea, precisión, satisfacción, reducción de quiebres, disposición de pago y rentabilidad siguen pendientes de medición real. La prueba de código no sustituye las sesiones con el propietario y los cinco bodegueros adicionales propuestos en el informe. El informe original no fue reescrito: estos archivos son documentación técnica de la implementación.
