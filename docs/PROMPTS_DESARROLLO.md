# ResiVe — Prompts de implementación por fases

Usar junto con `docs/PLAN_DESARROLLO.md`. Ejecutar en orden, una fase por vez. Cada fase entrega una parte funcional con backend y frontend integrados. No solicitar que una IA genere toda la plataforma de una vez.

## 00. Contexto maestro

Pega este bloque al iniciar un chat de desarrollo; después pega el prompt de la fase. Si el agente tiene acceso al repositorio, debe leer el plan en lugar de reconstruirlo de memoria.

```text
Desarrolla ResiVe, plataforma inmobiliaria venezolana enfocada en alquiler
residencial y con sección de venta. Lee AGENTS.md y docs/PLAN_DESARROLLO.md.
Respeta el alcance de la fase que te indique y conserva el trabajo existente.

Arquitectura obligatoria:
- Python y Django, plantillas HTML, CSS y JavaScript modular.
- HTMX para interacciones sin recargar el documento completo.
- PostgreSQL alojado en Supabase; ORM y migraciones Django.
- Fotografías en Cloudflare R2 mediante django-storages/boto3.
- Django Auth y sesiones; no duplicar identidad con Supabase Auth.
- Aplicación del mismo origen: navegador -> Django -> PostgreSQL/R2.
- No usar React, una SPA separada, una API REST duplicada ni microservicios.

Una cuenta puede buscar y publicar. Usa «Busco vivienda», «Publico inmuebles»
y «Anunciante» en la interfaz. Arrendatario significa inquilino, no propietario.
Prioriza móvil, conexiones lentas, accesibilidad y ubicaciones venezolanas.

Antes de editar, revisa lo existente, dependencias, rutas, formularios y pruebas
afectadas. Usa el grafo según AGENTS.md y fallback cuando no haya cobertura.
Reutiliza patrones del proyecto y aplica el cambio mínimo completo.

Cada fase incluye modelos/migraciones cuando correspondan, permisos,
formularios, vistas, plantillas, CSS/JS necesarios y pruebas de comportamiento.
No entregues botones sin funcionalidad, datos ficticios como reales ni TODOs
en el recorrido solicitado. No sobrescribas cambios ajenos.

Guarda precios con Decimal y moneda. No mezcles USD y VES al ordenar.
Comprueba pertenencia por objeto en servidor. Todas las escrituras usan CSRF.
Las URLs deben funcionar por entrada directa y con atrás/adelante.
Preserva errores y valores al validar formularios mediante HTMX.
Mantén secretos fuera de Git, HTML, JavaScript, capturas y logs.

Usa PostgreSQL desechable para pruebas. No ejecutes pruebas destructivas en
Supabase de producción. No inventes credenciales ni resultados de integración.
Si falta acceso externo, completa configuración y pruebas aisladas, documenta
la comprobación pendiente y no declares la fase verificada contra cloud.

Al terminar informa: qué funciona, archivos principales, migraciones y comandos,
pruebas ejecutadas y resultados, límites o verificaciones pendientes.
Actualiza docs/ESTADO_DESARROLLO.md con hechos, siguiente fase y bloqueos.
No despliegues en producción como parte de una fase de implementación local.
```

## 01. Convertir el plan en una base de trabajo

```text
Aplica el contexto maestro. Prepara la ejecución de ResiVe sin implementar
funciones todavía. Lee el plan y el repositorio; registra diferencias reales.

Entrega docs/BACKLOG.md con historias y criterios de aceptación agrupados por
fase, docs/DECISIONES.md con decisiones esenciales, y
docs/ESTADO_DESARROLLO.md con el punto de partida.

Incluye matriz de permisos, transiciones de publicación, rutas previstas,
campos de alquiler y venta y mapa de pantallas. Distingue requisitos del MVP,
mejoras posteriores y datos externos pendientes. Mantén el plan como fuente
principal y evita copiar todo su contenido en cada archivo.

Comprueba que cada historia tenga un recorrido de interfaz, una regla de
servidor y una forma de verificarla. Identifica especialmente privacidad de
direcciones, hilos, imágenes y exposición accidental mediante Supabase.
No diseñes pagos, contratos digitales ni chat en tiempo real en esta fase.
```

## 02. Django, Supabase y R2

```text
Implementa la base ejecutable de ResiVe conforme al contexto maestro.

Selecciona Python compatible y el parche mantenido de Django 5.2 LTS;
verifica documentación oficial y fija versiones reproducibles. Configura
psycopg, django-storages con S3/boto3 y Pillow. Crea configuración por entorno,
.env.example, .gitignore, arranque local y documentación de instalación.

Crea el usuario personalizado mínimo antes de la primera migración, con
correo como identificador, normalización y unicidad también en base de datos.
Incluye manager/admin compatibles; el resto de identidad se completa después.

Configura Supabase como PostgreSQL por DATABASE_URL con TLS y validación de
certificado. Documenta conexión directa o pooler de sesión según la red;
MIGRATION_DATABASE_URL solo para tareas administrativas desde red compatible.
Prepara esquema resive y roles separados de migración y runtime mediante
procedimiento reproducible. No concedas DDL al runtime. Verifica grants sobre
tablas/secuencias nuevas. No expongas el esquema por la Data API ni uses
Supabase JS, Auth, Storage o service_role en el frontend.

Configura STORAGES para R2 privado, endpoint de cuenta, región compatible,
credenciales limitadas y firmas temporales. No actives r2.dev ni dominio público.
No uses R2 como directorio local. Los estáticos del proyecto se sirven por el
despliegue. Documenta variables y diagnóstico sin imprimir secretos.

Crea una portada mínima real y una prueba de arranque. Añade pruebas de
configuración sin credenciales reales y un smoke test cloud optativo de
conexión SQL y subida/lectura/eliminación de un objeto temporal propio.
No ejecutes ese smoke test sobre datos del usuario. Si no hay credenciales,
deja instrucciones exactas y reporta la integración como no comprobada.
```

## 03. Identidad y estructura visual

```text
Implementa registro por correo, verificación con token firmado/expirable,
acceso, salida por POST, recuperación de contraseña y edición del perfil.
Reutiliza Django Auth y sus herramientas; no crees criptografía propia.
Comprueba que los tokens de verificación no se puedan reutilizar tras verificar
y que un cambio de correo requiera verificar la nueva dirección.

Toda cuenta puede activar «Publico inmuebles» sin perder favoritos ni consultas.
Correo verificado es requisito para enviar anuncios a revisión y contactar.
El perfil distingue propietario/asesor declarado; teléfono privado y contacto
por WhatsApp solo por consentimiento. No agregues verificación documental.

Construye base.html, navegación móvil/escritorio, componentes de formulario,
botones, avisos, carga, estados vacíos y páginas de error con CSS propio.
Configura HTMX local y módulos JS mínimos. Mantén mejora progresiva, foco,
CSRF, mensajes accesibles y manejo de sesión expirada en peticiones parciales.

Aplica límites de intentos con un mecanismo comprobado que funcione entre
workers; no uses un contador en memoria de proceso como protección productiva.
Documenta los límites. Evita respuestas que revelen si un correo existe.

Prueba duplicados de correo por mayúsculas, tokens expirados/reutilizados,
recuperación, cambio de correo, acceso no autenticado y formularios inválidos.
Comprueba navegación por teclado y valores preservados tras error HTMX.
```

## 04. Catálogo venezolano

```text
Implementa FederalEntity, Locality y Zone con claves de origen, nombres,
alias y relaciones. La interfaz usa Estado, Ciudad/localidad y Zona.
No identifiques ciudad con municipio ni inventes divisiones administrativas.

Implementa comando de importación CSV/JSON con contrato documentado,
simulación, transacción, informe de errores y actualizaciones idempotentes
por identificadores estables. Nunca borres ubicaciones usadas por anuncios.
Registra fuente, licencia, fecha y cobertura del conjunto importado.

Investiga una fuente nacional reutilizable y valida su licencia y estructura
antes de incorporarla. Si no se puede validar, entrega una muestra marcada
solo para desarrollo y registra el catálogo nacional como requisito pendiente;
no anuncies cobertura completa ni sustituyas todo el país por sus capitales.

Implementa selectores dependientes con HTMX: cambiar entidad limpia localidad
y zona, cambiar localidad limpia zona. Backend valida esas mismas relaciones.
Contempla homónimos, tildes y localidades metropolitanas sin perder el padre
administrativo. Agrega flujo de solicitud de localidad faltante para revisión.

Prueba importación repetida, actualización, referencia inválida, duplicados,
reversión ante error y combinación manipulada de estado/ciudad/zona.
```

## 05. Anuncios y editor completo

```text
Implementa Listing, servicios y estados según el plan. Una publicación tiene
operación alquiler o venta, dueño, ubicación, moneda, precio y características.
No agregues un modelo separado de inventario sin necesidad real.

Crea panel Mis publicaciones y editor por pasos con borrador persistente:
información, ubicación, precio/condiciones, fotos y revisión. Implementa ahora
los pasos de datos y deja la carga para la fase 06 con aviso explícito, no éxito
simulado. El borrador puede estar incompleto; enviar a revisión exige todos
los campos requeridos y al menos una foto procesada.

Alquiler lleva mensualidad, condiciones declaradas y disponibilidad. Venta
lleva precio total y campos propios. Dinero con Decimal; no float. Valida
campos por operación, magnitudes no negativas y ubicación coherente.
No expongas dirección exacta en vistas públicas.

Solo el dueño edita. Estado, dueño y verificación no se aceptan desde el cliente.
Implementa transiciones explícitas reutilizables por vistas y admin, con
transacciones donde haya escrituras relacionadas. Reenviar cambios
sustanciales de un anuncio publicado lo oculta hasta nueva revisión;
explica el efecto al usuario. Aún no apruebes automáticamente anuncios.

Prueba usuario ajeno, manipulación de dueño/estado, valores monetarios,
borrador incompleto, validación de envío, cambio de operación y transiciones
inválidas. Verifica el guardado parcial sin pérdida de datos ni recarga global.
```

## 06. Fotografías reales en Cloudflare R2

```text
Completa el paso de fotos y el modelo ListingImage. Usa el storage existente.
Carga una foto por petición a Django, máximo 15 por anuncio, 8 MB y 25 MP
por archivo. Configura límites en proxy y servidor. Verifica propiedad y cuota
también con cargas concurrentes; no confíes en controles del navegador.

Comprueba formato decodificando con Pillow, limita memoria/píxeles, rechaza
archivos corruptos y SVG, corrige orientación y elimina EXIF/GPS. Genera
versiones optimizadas y miniaturas. Conserva claves aleatorias y metadatos
en PostgreSQL, no URLs firmadas ni nombres de archivo confiados al cliente.

Implementa vista previa, estado de carga, error/reintento, elección de portada,
orden y eliminación mediante controles accesibles, sin requerir arrastrar.
El endpoint de lectura autoriza según publicación o dueño/moderador y redirige
a GET firmado de cinco minutos. Protege redirecciones privadas con no-store;
no asumas que una URL firmada ya emitida se revoca al ocultar el anuncio.

Gestiona el fallo entre R2 y base: limpieza compensatoria de cargas fallidas,
borrado después del commit y reconciliación idempotente con simulación y
período de gracia. Nunca borres objetos aún referenciados. Mantén el bucket
privado; no añadas carga directa desde navegador ni un Worker en esta fase.

Prueba archivo falso/corrupto, exceso de tamaño/píxeles/cantidad, EXIF retirado,
acceso a borrador ajeno, fallo R2, fallo SQL y borrado repetido. Usa storage
aislado en tests y smoke test R2 en staging cuando existan credenciales.
```

## 07. Búsqueda, resultados y detalle

```text
Implementa inicio, /alquileres/, /ventas/ y detalle con datos reales del ORM.
Alquiler es la opción principal. Filtra por entidad, localidad, zona, tipo,
moneda/presupuesto, dormitorios, baños, estacionamiento, amueblado, mascotas
y servicios aplicables. Solo aparecen publicaciones públicas disponibles.

Valida parámetros GET; permite compartir la URL completa con sus filtros.
Ordena por recientes o por precio solo dentro de una moneda. Agrega paginación
estable, select_related/prefetch_related e índices para consultas demostradas.
Una búsqueda vacía ofrece limpiar filtros, no anuncios inventados.

Resultados y contador se actualizan juntos mediante HTMX, con debounce,
cancelación de respuestas obsoletas, indicador de carga y URL actualizada.
Implementa el contrato de página completa/fragmento/restauración de historial.
No rompas recarga directa, atrás/adelante ni el formulario GET sin JavaScript.

Detalle con galería, precio claramente mensual o total, gastos separados,
ubicación aproximada, servicios, anunciante y disponibilidad declarada.
Dirección exacta fuera de HTML, atributos, scripts y metadatos públicos.
Fotos accedidas a través del endpoint autorizado ya implementado.

Prueba filtros combinados, moneda, visibilidad por estado, parámetros inválidos,
paginación, slug canónico y ausencia de datos privados. Verifica en navegador
que filtrar no recarga el documento y que el historial recupera el estado.
```

## 08. Favoritos y paneles

```text
Implementa favoritos únicos por usuario/anuncio y página Mis favoritos.
La escritura expresa estado deseado (guardado sí/no), para que un reintento
no invierta accidentalmente el resultado. Usa POST con CSRF y autorización.

Actualiza botón, aria-pressed, texto y avisos sin recarga; si falla la petición,
no dejes la interfaz mostrando un guardado que no existe. Tras autenticación,
retorna a una URL interna validada y permite completar la acción.

Completa panel del anunciante con filtros por estado, edición, envío a revisión,
pausa y cierre como alquilado o vendido según operación. Los favoritos de
anuncios retirados muestran indisponibilidad sin revelar contenido privado.

Implementa perfil y preferencias pendientes de fases anteriores. Permite
solicitar eliminación de cuenta; define y documenta qué se elimina o anonimiza
y qué requiere retención justificada. No borres conversaciones de terceros
mediante cascadas accidentales ni prometas borrado inmediato de backups.

Prueba favoritos repetidos/concurrentes, usuario ajeno, fallo de red, retorno
de autenticación seguro y panel coherente con el estado real del anuncio.
```

## 09. Consultas, visitas y notificaciones

```text
Implementa Inquiry, Message, VisitRequest, UserBlock, Notification y entrega
de correo reintentable. Usa hilos privados por anuncio/interesado/anunciante,
sin WebSockets ni Supabase Realtime. Evita crear hilos duplicados con una
restricción en base de datos. Impide consultas sobre anuncios no disponibles
y consultas del anunciante a su propio anuncio.

Solo participantes leen/escriben hilos. Los mensajes son texto plano y se
escapan. Aplica límites de envío y bloqueo entre usuarios. No des acceso
general a mensajes al moderador; una denuncia solo expone el material
necesario para resolverla, con acceso restringido y registro de consulta.

Solicitudes de visita con horario en America/Caracas, almacenamiento UTC,
aceptación, rechazo, cancelación y propuesta alternativa. Reprogramar exige
nueva confirmación. Controla actualizaciones concurrentes y fechas pasadas.
Una visita no reserva ni cobra el inmueble.

Interfaz de bandeja, hilo y visitas mediante HTMX; refresco manual de mensajes
y notificaciones en el MVP. Las notificaciones pertenecen a un destinatario.
Persiste eventos de correo y ejecuta entrega con comando programado y
reintentos idempotentes. Fallo SMTP no pierde ni duplica mensajes guardados.

WhatsApp solo como enlace optativo consentido; no envíes mensajes por el
usuario ni presentes clics como operaciones cerradas. No incluyas dirección
exacta ni mensajes completos en correos.

Prueba aislamiento de participantes, bloqueo, anuncio cerrado, spam, duplicados,
concurrencia de visitas, fallo SMTP y destinatarios de las notificaciones.
```

## 10. Moderación y prevención de abuso

```text
Implementa moderación operativa usando Django Admin y los permisos existentes.
Cola de anuncios, aprobación, rechazo con motivo, retirada y revisión de
denuncias. Reutiliza las transiciones de dominio; el admin no debe saltarse
validaciones, propiedad de imágenes ni requisitos de publicación.

Crea formularios de denuncia para anuncios y mensajes visibles al reportante,
categorías, estado, resolución y registro de actor/fecha/motivo. Aplica límites
y protege contra denuncias duplicadas accidentales. No añadas un sistema de
reputación ni insignias de propiedad comprobada.

La suspensión de un anunciante retira sus anuncios de resultados y evita
nuevas firmas de imágenes privadas o retiradas. Debe afectar también sesiones
existentes mediante comprobación de estado. Documenta qué ocurre con sus
consultas y notificaciones. No borres automáticamente evidencia necesaria.

Restringe acceso del personal por grupos y permisos; registra acciones
sensibles y evita cambios silenciosos en auditoría. Ofrece al anunciante un
motivo comprensible y una vía de revisión mediante soporte.

Prueba aprobación por usuario no autorizado, edición que evade revisión,
suspensión con sesión activa, retirada de imágenes y acceso indebido a
denuncias/conversaciones. Comprueba el recorrido publicar-revisar-aprobar.
```

## 11. Accesibilidad, rendimiento y SEO

```text
Revisa los recorridos completos existentes, sin rediseñar ni añadir funciones.
Corrige móvil, teclado, etiquetas, contraste, foco tras swaps, aria-live,
galería, errores de formularios y reducción de movimiento.

Verifica HTMX con respuestas 422, 403, 429 y 500, sesión expirada, desconexión,
clics repetidos, respuestas fuera de orden y atrás/adelante. Comprueba Vary,
caché privada e historial sin snapshots de información sensible.

Optimiza consultas demostradas, miniaturas, srcset, lazy loading y recursos
estáticos. Mide páginas clave con datos de prueba representativos. Registra
el entorno y valores medidos; no inventes puntuaciones ni garantías de carga.

Implementa títulos, descripciones, canonical y sitemap solo para publicaciones
públicas. Noindex para paneles y resultados de filtros sin valor editorial.
Las páginas de entidad/ciudad deben tener contenido útil antes de indexarlas.
Usa imagen social de marca estable; no guardes firmas temporales como og:image.

Prueba entradas directas, fallback sin JS, datos privados ausentes, navegación
fluida sin recarga del documento y consultas sin N+1 en listado y detalle.
Entrega resultados y límites concretos de la revisión.
```

## 12. Seguridad y pruebas de aceptación

```text
Ejecuta una revisión acotada de seguridad y aceptación de ResiVe.
Lee configuración y pruebas antes de añadir otras; prioriza riesgos reales.

Verifica CSRF en escrituras, XSS en descripciones/mensajes, permisos por objeto,
session cookies, redirecciones de login, límites de intentos, carga de archivos,
fuga de secretos, caché y logs. Verifica que el esquema resive no esté accesible
por Data API y que runtime no tenga permisos de migración. Nunca interpretes
tests locales como comprobación de la configuración cloud real.

Añade o completa Playwright para: registro/verificación/acceso; publicación
con fotos; moderación; búsqueda por estado/ciudad; favorito; consulta; visita;
cierre de anuncio. Usa correo y storage aislados y PostgreSQL desechable.
Prueba dos usuarios y un tercero atacante en todos los objetos privados.

Comprueba no recarga completa durante filtros, favoritos y mensajes con una
señal de navegación del documento, no solo por inspección visual. Simula
fallos de red, Supabase, R2 y SMTP donde corresponda sin tocar producción.

Entrega docs/ACEPTACION.md con pruebas ejecutadas, resultados, fallos abiertos
y comprobaciones externas pendientes. Corrige los fallos dentro del alcance;
no declare listo para producción si hay riesgos críticos no resueltos.
```

## 13. Staging y preparación del lanzamiento

```text
Prepara el despliegue de ResiVe en un hosting Linux para Python persistente,
Supabase PostgreSQL y R2 privado. No despliegues en producción automáticamente.
Si falta elegir hosting, crea artefactos portables y documenta los requisitos
sin inventar una URL desplegada ni contratar servicios.

Incluye arranque WSGI, collectstatic, HTTPS/proxy, DEBUG=False, hosts/orígenes,
límites de subida, health checks, logs sin datos sensibles y tareas programadas
de correo y reconciliación. Ejecuta check --deploy con configuración apropiada.
Dimensiona conexiones SQL según workers y límites reales; sin multiplicar
pools innecesariamente. Separa secretos runtime de migraciones.

Documenta creación de recursos por entorno, TLS, esquema/grants de Supabase,
Data API deshabilitada/no expuesta, permisos de R2 y r2.dev desactivado,
credenciales, correo y recuperación de fallos. No registres secretos en logs.

Prepara backups de PostgreSQL y objetos R2, retención y procedimiento de
restauración coherente. Prueba restauración en un entorno aislado cuando
existan recursos. Planifica migraciones compatibles, rollback de aplicación
y recuperación de datos sin suponer que revertir código revierte una migración.

Entrega docs/OPERACION.md y checklist de lanzamiento: dominio, recursos,
smoke tests SQL/R2, correo real, catálogo nacional/licencia, política de
moderación, contenidos de privacidad/términos revisados y aceptación completa.
Marca lo no verificado con claridad y conserva los logs de comprobación sin
secretos. No afirmes que una copia de PostgreSQL respalda los archivos R2.
```

## Prompt de continuación

```text
Retoma ResiVe. Lee AGENTS.md, docs/PLAN_DESARROLLO.md,
docs/ESTADO_DESARROLLO.md y el estado real de Git. No rehagas fases terminadas.
Identifica la primera fase incompleta y ejecuta su prompt correspondiente
de docs/PROMPTS_DESARROLLO.md bajo el contexto maestro.
Si la documentación contradice el código, verifica la situación y registra
la diferencia antes de avanzar. Conserva Supabase PostgreSQL y Cloudflare R2.
```

## Cómo saber que una fase terminó

No basta con que el agente diga «implementado». Deben existir la interfaz y el recorrido solicitado, validaciones en servidor, permisos, persistencia correcta y evidencia de las pruebas pertinentes. Una integración simulada debe seguir etiquetada como simulada hasta comprobarla contra el entorno correspondiente.

No usar estos prompts para ejecutar todos los cambios en producción sin revisión. Los pasos preparan una aplicación comprobable; los servicios reales, datos territoriales y validaciones de lanzamiento deben verificarse con evidencia.
