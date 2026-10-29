# ResiVe — Estado de desarrollo

Fecha: 28 de octubre de 2026. Hay una aplicación Django ejecutable con interfaz integrada; aún no hay lanzamiento público ni servicios cloud verificados con credenciales reales.

## Implementado

- Acceso y vinculación explícita con Google mediante OpenID Connect, PKCE y Authlib; configuración en GOOGLE_OAUTH.md.

- Cuenta por correo, unicidad, verificación revocable, acceso/salida, recuperación/cambio de contraseña, perfil y preferencias.
- Catálogo de entidades/localidades, importación JSON idempotente con simulación y solicitudes de ubicaciones faltantes.
- Publicaciones de alquiler/venta, borradores, editor, fotos procesadas, orden y eliminación, revisión y estados.
- Búsqueda, filtros, moneda explícita, detalle, favoritos, enlaces directos y actualizaciones HTMX.
- Consultas privadas, mensajes con clave de reintento, visitas versionadas, lectura y bloqueos.
- Notificaciones por usuario, preferencias y outbox SMTP con reintentos.
- Enlace WhatsApp opcional para anunciantes activos con correo verificado y teléfono internacional válido; desactivado no publica el número.
- Denuncias de anuncios/mensajes, evidencia limitada, resolución y auditoría de acceso; revisión de anuncios en Django Admin.
- Configuración Supabase PostgreSQL y R2 privado, secretos por entorno, controles de caché/permisos y modo local explícito.
- Sitemap, robots, páginas de información, límites de intentos y mantenimiento.

## Evidencia registrada

101/101 pruebas aprobadas sobre PostgreSQL 17.6 local, incluidas tres pruebas con Chrome en móvil/escritorio y un recorrido con JavaScript desactivado. Las interacciones HTMX conservaron el documento sin recargar. Se verificaron migraciones con rol migrador y permisos limitados de ejecución en un esquema separado. Ruff, comprobación Django y ausencia de migraciones pendientes aprobados. Detalle y límites en [ACEPTACION.md](ACEPTACION.md).

## Diferencias respecto al plan

- Editor en una pantalla agrupada con borrador y fotos; no asistente de cinco pantallas.
- Perfil dentro del usuario personalizado, sin tabla Profile adicional.
- Cierre con estado común `closed`; la operación conserva alquiler o venta.
- Auditoría de publicaciones denominada ListingTransition; denuncias con registro separado.
- Administración interna con Django Admin, sin panel de soporte duplicado.
- Importación JSON; no se añadió un segundo formato CSV.
- GeoNames aporta 25 entidades del origen y 20.709 localidades; requiere revisión territorial y aún no incluye zonas curadas.
- El modo local usa SQLite/archivos; el destino de despliegue sigue siendo Supabase/R2.
- Correo y mantenimiento son comandos programables; su programación efectiva depende del despliegue.

## Pendientes de lanzamiento

Configurar staging real, comprobar TLS/grants/buckets y recepción SMTP; medir rendimiento/accesibilidad; revisar catálogo y textos legales; publicar soporte y ensayar restauración conjunta. La validación local global y los recorridos de navegador ya se ejecutaron.

La eliminación de cuenta registra una solicitud humana; no borra automáticamente conversaciones o copias. Las visitas no reservan ni cobran. Pagos, contratos digitales, suscripciones, mapa, móvil y chat en tiempo real pertenecen a evolución posterior.

Siguiente paso operativo: seguir [OPERACION.md](OPERACION.md), ejecutar pruebas sobre PostgreSQL desechable y comprobar integraciones en staging. Mantener credenciales fuera del repositorio.
