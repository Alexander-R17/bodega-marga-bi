# Bodega Marga: app Android nativa 0.5 y actualización 14

Las pantallas móviles se construyen con vistas Android (`LinearLayout`, `ScrollView`,
`EditText`, tarjetas, imágenes y diálogos), con la paleta crema, verde y durazno del
sistema web. No hay una WebView ni un enlace que sustituya el catálogo por el navegador.

La app contiene acceso, Tienda, Carrito, Inventario, Perfil y cámara. La caja de cobro,
los tickets y el BI siguen en la web existente. La app prepara ese mismo carrito y
permite crear productos y registrar movimientos según el rol; no incluye todavía
un segundo flujo de cobro nativo que compita con el flujo Yape ya utilizado.

## Identidad y permisos

Se conserva el proyecto Firebase. La app usa su API REST oficial para iniciar sesión
y renovar la sesión. La contraseña se envía únicamente a Firebase mediante HTTPS y
no se guarda. El refresh token queda cifrado con AES/GCM y Android Keystore; el ID
token se mantiene en memoria. La configuración de la tienda solo incluye el endpoint
público, y el bootstrap devuelve la configuración Firebase pública. No se instala
una cuenta de servicio ni una clave de Supabase dentro del APK.

La función `tienda-movil` valida criptográficamente RS256 con las claves públicas de
Google, exige issuer, audience y proyecto correctos, correo verificado y token vigente.
Consulta también la cuenta para comprobar deshabilitación y revocación, con un máximo
de 60 segundos de caché. Cada operación SQL vuelve a comprobar UID, email y rol en el
equipo privado. Un UID o rol enviado en el cuerpo no reemplaza la identidad verificada.

El administrador activa y sincroniza el equipo desde la web. Los roles proceden de
los Secrets y los nombres/UID de Firebase. Debe repetir la sincronización después de
cambiar esos roles o nombres; la copia móvil no interpreta cambios de Secrets hasta
esa sincronización. La deshabilitación en Firebase protege todos los accesos, con el
límite de caché descrito. El backend deniega modificaciones de inventario a cajeros y
analistas. Las tablas y funciones nuevas no se abren a `anon` ni `authenticated`.

## Carrito compartido e integridad

El carrito canónico vive en Supabase y se identifica por UID. Dos dispositivos de
la misma cuenta preparan el mismo carrito; cuentas diferentes mantienen carritos
separados. El catálogo y el inventario son comunes a toda la bodega.

La revisión del carrito detecta cambios concurrentes y obliga a cargar la versión
actual en vez de sobrescribirla. Los comandos tienen UUID y resultado persistente:
si se pierde una respuesta se reintenta el mismo comando, sin duplicar una entrada
ni volver a agregar una unidad. La app conserva un cambio sin confirmación asociado
a su usuario y tienda antes de permitir otra modificación.

La web consulta cambios cada tres segundos y la app cada cuatro mientras están
activas. Solo se recarga catálogo cuando cambia su revisión; la app pagina cuarenta
productos y no descarga BI para cada escaneo. La actualización requiere conexión y
puede tardar más si la red o el alojamiento están lentos. No se promete actualización
instantánea o disponibilidad sin conexión.

Antes de cobrar en la web se bloquea el carrito. Las mutaciones remotas se rechazan
hasta completar o cancelar esa operación. La venta original sigue comprobando stock,
precios, total y UUID en su transacción. Un carrito no reserva existencias: otro
cajero puede vender unidades antes de confirmar, y el servidor vuelve a validarlas.
Si se pierde la respuesta de una venta ya completada, la consulta del carrito reconoce
la operación confirmada y lo vacía una sola vez. Una operación sin venta no se presenta
como exitosa ni se limpia automáticamente como si estuviera pagada.

Las fichas de producto tienen una revisión independiente de los cambios de cantidad
en stock. La edición nativa y la nueva ruta de guardado web rechazan una ficha obsoleta.
Los movimientos siguen usando la función transaccional original y conservan el UID
del responsable. Crear una ficha nunca agrega stock por sí solo.

## Cámara y códigos

ZXing core 3.5.3 decodifica localmente códigos de barras EAN/UPC, Code 128/39, ITF y QR.
La cámara devuelve el texto a la interfaz nativa; no envía fotografías al servidor ni
abre la URL contenida en un QR. Una lectura equivale a una acción de agregar una unidad,
y vuelve al catálogo para evitar repetir el mismo fotograma como varias compras.

El código debe existir o asociarse una vez a la ficha del negocio. No se consulta un
catálogo universal de marcas. Un QR publicitario común a varias presentaciones no las
distingue. Para productos sin código se conserva el registro y la selección manual.
Las cantidades permanecen enteras; la venta fraccionada por peso requiere otra ampliación.

El lector de productos y el receptor Yape son funciones distintas. La actualización
mantiene el mismo paquete, certificado, preferencias y credencial cifrada del receptor.
La cámara requiere su permiso propio y el sistema móvil requiere acceso Firebase. El
lector Yape del dispositivo autorizado puede seguir activo al cerrar sesión del catálogo.

## Despliegue y verificación

Sigue `LEEME_APP_NATIVA_14.txt`. Sobre la instalación operativa anterior ejecuta solo
SQL 14, publica `tienda-movil`, reinicia Streamlit y activa/sincroniza el equipo. No
hace falta instalar SQL 13 ni publicar `recibir-escaneo` para esta versión. La función
nueva utiliza JWT Firebase propios, por lo que se desactiva solo su verificación JWT
heredada de Supabase. Su código sigue exigiendo y validando autenticación.

Los informes `20_VERIFICACION_SQL.json` y `20_VERIFICACION_DESARROLLO.json` describen
las pruebas aisladas. No se accedió a datos de producción. Se comprobó la compilación,
firma y alineación del APK, y la decodificación con imágenes sintéticas. La cámara y
la apariencia real en el S23 Ultra necesitan la prueba física del usuario. No se
presenta un diseño simulado como una captura de la app ejecutándose.

Fuentes técnicas:

- https://firebase.google.com/docs/reference/rest/auth
- https://firebase.google.com/docs/auth/admin/verify-id-tokens
- https://github.com/zxing/zxing/tree/zxing-3.5.3
- https://developer.android.com/reference/android/widget/package-summary
- https://supabase.com/docs/guides/functions
