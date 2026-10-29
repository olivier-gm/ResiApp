# ResiVe — Operación

Procedimiento para desarrollo y preparación de staging. Su presencia no confirma un despliegue ni una restauración ejecutada. Los secretos se suministran por entorno; nunca se guardan aquí.

## Entornos y arranque

El README describe el arranque local. `LOCAL_DEMO=1` exige `DJANGO_DEBUG=1` y usa SQLite y archivos privados locales. Con `LOCAL_DEMO=0`, la aplicación exige PostgreSQL, credenciales R2 y una clave Django propia. No hay fallback silencioso a almacenamiento local en ese modo.

Staging y producción deben tener proyectos/buckets separados y cuentas administrativas individuales. Establece `PUBLIC_BASE_URL` con el origen HTTPS correcto: se usa para enlaces de verificación, recuperación y notificaciones. Configura `DJANGO_ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` con los hosts/orígenes exactos.

Sirve la aplicación mediante WSGI detrás de un proxy HTTPS. `TRUST_PROXY_SSL=1` solo corresponde cuando el proxy de confianza sobrescribe `X-Forwarded-Proto` e impide el acceso directo no confiable al backend. Ejecuta `collectstatic` al construir cada versión. La ruta `/healthz/` confirma que el proceso responde; no comprueba PostgreSQL, R2 ni SMTP.

## Supabase y migraciones

1. Crea un proyecto dedicado y selecciona región, límites y respaldo según la operación prevista.
2. Revisa `infra/supabase.sql` como plantilla. Sustituye sus contraseñas/identificadores mediante un canal seguro y ejecútala con una cuenta administrativa en el proyecto correcto.
3. Usa el esquema `resive`, el rol de migraciones `resive_migrator` y el de ejecución `resive_runtime`.
4. Configura `MIGRATION_DATABASE_URL` con el rol migrador y `DATABASE_URL` con el runtime. Usa conexión directa si la red lo permite; para backend persistente solo IPv4, considera el pooler de sesión según el proyecto. Las migraciones requieren una sesión compatible.
5. Mantén `DATABASE_SCHEMA=resive`. Configura TLS con `sslmode=verify-full` y la raíz de confianza requerida por libpq/proveedor, por ejemplo mediante `sslrootcert` en la URL. No desactives la comprobación de certificado para resolver problemas de red.
6. En una terminal administrativa, activa temporalmente `RESIVE_MIGRATE=1`, ejecuta `migrate`, `import_locations`, `setup_roles` y `createsuperuser`. El runtime no debe recibir `MIGRATION_DATABASE_URL` ni `RESIVE_MIGRATE`.
7. Comprueba que los privilegios por defecto del rol migrador conceden al runtime solo el acceso necesario a tablas y secuencias nuevas. Verifica que no tenga DDL, propiedad del esquema ni privilegios administrativos.

En PowerShell, las tareas administrativas usan:

```powershell
$env:RESIVE_MIGRATE='1'
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py setup_roles
Remove-Item Env:RESIVE_MIGRATE
```

La plantilla SQL requiere revisión y sustitución; no la ejecutes sin comprobar cuenta y proyecto de destino. Crea el esquema antes de la primera migración. No ejecutes el runner de pruebas con estas conexiones reales: usa una base desechable expresamente destinada a pruebas.

### Aislamiento de la Data API

Mantén `resive` fuera de los esquemas expuestos. Si la Data API no se utiliza en el proyecto dedicado, desactívala y comprueba los grants efectivos de `anon` y `authenticated`. Una sesión Django no crea contexto de Supabase Auth: `auth.uid()` no identifica automáticamente al usuario de Django. Los permisos por usuario los comprueba el backend en cada objeto.

No se necesita publicar claves Supabase en JavaScript ni utilizar `service_role` para la interfaz.

## R2 y ciclo de archivos

Crea un bucket privado por entorno y una credencial limitada a ese bucket con los permisos necesarios de lectura, escritura y eliminación. Configura `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` y `R2_BUCKET_NAME`. Desactiva acceso público, dominios públicos y `r2.dev`.

Las fotografías se envían a Django, se decodifican y transforman a WebP con miniatura, corrigen orientación y retiran EXIF. Límites: 15 fotos por anuncio, 8 MB por archivo y 25 megapíxeles. Alinea el límite de petición del proxy con el backend. No se solicitan documentos de identidad en esta versión.

El endpoint de lectura consulta estado y permisos antes de firmar un GET de cinco minutos. No compartas caché de paneles, redirecciones privadas ni páginas con estado de sesión. Una firma ya emitida sigue válida hasta vencer; una copia descargada no se revoca.

PostgreSQL y R2 no comparten una transacción. La aplicación intenta compensar cargas fallidas y difiere borrados hasta el commit; los fallos se revisan con el reconciliador. Ejecuta primero:

```text
python manage.py reconcile_photos
```

Es una simulación. Revisa referencias y entorno antes de `reconcile_photos --delete`. La gracia predeterminada es 48 horas y no se admite menos de 24. El comando se limita al prefijo `listings/`; no sustituye un respaldo.

## Correo y tareas programadas

Configura SMTP, puerto, credenciales, remitente y TLS por entorno. Publica y valida SPF/DKIM/DMARC según el proveedor y verifica recepción, no solo aceptación SMTP. Los correos se guardan en `EmailDelivery`; un fallo SMTP no deshace consultas ni publicaciones guardadas.

| Frecuencia propuesta | Comando | Propósito |
|---|---|---|
| Cada minuto | `python manage.py send_emails --limit 50` | Enviar pendientes y reintentar fallos |
| Diario | `python manage.py cleanup_rate_limits` | Retirar ventanas expiradas |
| Diario, revisión inicial | `python manage.py reconcile_photos` | Detectar huérfanos sin borrar |

Programa estos comandos en el entorno de la aplicación. Sus conexiones se suman a las de los workers. `send_emails` bloquea la fila durante la entrega y guarda intentos, siguiente intento y tipo de error sin detalles secretos.

La entrega SMTP es **al menos una vez**. Si el servidor acepta un correo y el proceso falla antes de guardar `sent_at`, el reintento puede duplicarlo. Un `Message-ID` estable no garantiza deduplicación del proveedor. Si esa garantía resulta necesaria, usa un proveedor con claves idempotentes. Verificación y recuperación son correos esenciales; la preferencia del usuario controla los avisos de consultas y visitas.

Los límites de intentos usan ventanas compartidas en base de datos. `TRUST_PROXY_SSL=1` confía también en `X-Real-IP` para los límites anónimos: úsalo únicamente cuando el origen solo sea accesible a través de un proxy propio que sobrescriba esa cabecera y `X-Forwarded-Proto`. La plantilla nginx lo hace. En otro caso deja la opción desactivada y usa `REMOTE_ADDR`; nunca aceptes esas cabeceras directamente de Internet.

## Comprobaciones cloud optativas

Solo en un entorno de desarrollo declarado, con credenciales reales suministradas por su operador:

```powershell
$env:RESIVE_CLOUD_CHECK_ALLOWED='1'
.venv/Scripts/python manage.py cloud_check --confirm-development-target
Remove-Item Env:RESIVE_CLOUD_CHECK_ALLOWED
```

El comando rechaza `LOCAL_DEMO`, exige PostgreSQL y storage S3 privado configurado, ejecuta `SELECT 1` y escribe, lee y elimina un objeto aleatorio bajo `smoke-check/`. No imprime credenciales ni URLs firmadas. Si falla la eliminación, revisa ese prefijo antes de repetir. La privacidad efectiva del bucket se comprueba también en Cloudflare.

El operador puede añadir `--smtp-to correo-propio@dominio`. Eso envía un mensaje real a la dirección indicada: el resultado confirma aceptación por SMTP; el destinatario debe comprobar la llegada. No hay destinatario automático ni envío externo en pruebas unitarias.

## Moderación y soporte

`setup_roles` crea el grupo **Moderadores**. Un administrador asigna ese grupo e `is_staff` únicamente a cuentas autorizadas. El grupo revisa publicaciones, denuncias y solicitudes de localidades; no obtiene acceso general a hilos privados.

La revisión utiliza Django Admin y registra actor, transición y motivo. Las denuncias de mensajes conservan la evidencia denunciada y registran acceso del personal sin abrir todo el hilo. Consulta las decisiones y razones registradas al atender un caso.

Suspender una cuenta impide utilizar sus sesiones y retira sus anuncios de la vista pública. La eliminación de cuenta es una solicitud para gestión humana: define anonimización, conservación justificada de conversaciones/denuncias y tratamiento de respaldos antes de completar cada caso. No realices cascadas de borrado para resolver solicitudes.

Antes del lanzamiento publica un canal de soporte real y revisa los borradores de privacidad, condiciones y ayuda. Correo verificado confirma acceso al correo; no certifica identidad ni propiedad inmobiliaria.

## Copias, restauración y cambios

Define retención, responsables y ubicación de las copias. Objetivos propuestos: RPO de 24 horas y RTO de ocho horas, sujetos a una restauración medida. No son garantías verificadas.

Respalda PostgreSQL y los objetos R2 por separado. Conserva un manifiesto de claves, marcas temporales y versión de aplicación para relacionarlos. Cifra y restringe acceso a las copias; contienen datos privados. Revisa la cobertura real del plan Supabase contratado y no supongas que una copia PostgreSQL incluye R2.

Ensaya en entorno aislado: restaurar esquema/datos, reponer objetos, verificar referencias, abrir un anuncio con foto y un hilo autorizado, y comprobar que un tercero no puede leerlo. Documenta fecha, duración, pérdidas observadas y recuperación de correos pendientes sin reenvíos masivos no deseados.

Antes de migrar en cloud: respaldo reciente, prueba en staging, compatibilidad código/esquema y plan de recuperación. Revertir código no revierte automáticamente datos ni migraciones. Ejecuta `check --deploy` con configuración real y revisa hosts, origen, TLS, cookies, secretos y logs.
