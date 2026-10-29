# ResiVe

Plataforma inmobiliaria para Venezuela enfocada en alquiler residencial, con una sección de venta. Una misma cuenta puede buscar vivienda y publicar inmuebles.

Aplicación Django con plantillas HTML, CSS propio, JavaScript y HTMX para navegar, filtrar y enviar formularios sin recargar el documento. La configuración cloud usa **PostgreSQL en Supabase** y **fotografías en un bucket privado de Cloudflare R2**.

## Qué incluye

- Cuentas por correo, verificación, recuperación de contraseña, perfil y preferencias.
- Anuncios de alquiler y venta, borradores, fotografías optimizadas y revisión por moderación.
- Búsqueda por estado, localidad, tipo, servicios y presupuesto en USD o VES.
- Favoritos, consultas privadas, solicitudes de visita, bloqueos y denuncias.
- Contacto por WhatsApp opcional, solo con autorización del anunciante y un número internacional válido.
- Notificaciones y bandeja de correos con reintentos.
- Administración con permisos, historial de transiciones y registro de acceso a denuncias.
- Catálogo importable de localidades, diseño adaptable, sitemap y controles de privacidad.

Es una implementación funcional de desarrollo. La conexión con los servicios reales, la revisión territorial y los requisitos de lanzamiento se comprueban por separado; consulta [el estado del proyecto](docs/ESTADO_DESARROLLO.md).

## Inicio rápido en Windows

Requiere Python 3.14, la versión usada en desarrollo, o una versión compatible con las dependencias fijadas.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py import_locations --dry-run
.venv/Scripts/python manage.py import_locations
.venv/Scripts/python manage.py setup_roles
.venv/Scripts/python manage.py createsuperuser
.venv/Scripts/python manage.py runserver
```

Abre [ResiVe local](http://127.0.0.1:8000/) y [la administración](http://127.0.0.1:8000/admin/). `.env.example` habilita explícitamente `LOCAL_DEMO=1` y `DJANGO_DEBUG=1`: usa SQLite y archivos locales para probar sin credenciales cloud. Ese modo no se admite con DEBUG desactivado ni representa una conexión a Supabase/R2. No se crean contraseñas universales ni cuentas automáticamente.

En Linux/macOS usa `.venv/bin/python` en los mismos comandos. Antes de copiar `.env.example`, conserva cualquier `.env` ya configurado.

El registro guarda el correo de verificación en una bandeja de salida. En otra terminal ejecuta periódicamente:

```powershell
.venv/Scripts/python manage.py send_emails --limit 50
```

En modo local, el contenido del correo aparece en la consola de ese comando. Abre el enlace y confirma la verificación para publicar y contactar. El administrador creado por `createsuperuser` tiene correo verificado y puede aprobar anuncios desde `/admin/`.

Para explorar opcionalmente con datos de muestra, en modo local y con una contraseña elegida por ti:

```powershell
.venv/Scripts/python manage.py seed_demo --password 'TU-CONTRASENA-LOCAL'
```

La cuenta es `demo@resive.local`; los anuncios creados se identifican como muestras, no ofertas reales. El comando exige modo local. No reutilices una contraseña personal o de producción.

## Supabase y Cloudflare R2

Para activar «Continuar con Google», configura `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` y el callback de Google Cloud conforme a [GOOGLE_OAUTH.md](docs/GOOGLE_OAUTH.md). El correo/contraseña sigue disponible. Las cuentas existentes vinculan Google desde Mi cuenta después de autenticarse; no hay vinculación automática por coincidencia de correo.

Usa `.env` con `LOCAL_DEMO=0`, `DJANGO_DEBUG=0`, una clave Django propia y las variables de PostgreSQL, R2 y correo. Las credenciales permanecen en el servidor. Supabase se utiliza como PostgreSQL; la identidad y los permisos de usuarios pertenecen a Django.

Prepara el esquema y los roles con la plantilla `infra/supabase.sql`; aplica las migraciones con el rol migrador y arranca con el rol runtime. Mantén el esquema fuera de la Data API y el bucket sin acceso público ni `r2.dev`. Las fotos se sirven tras autorización mediante URLs firmadas de cinco minutos.

La guía de conexión, TLS, permisos, tareas programadas, respaldos y comprobaciones está en [OPERACION.md](docs/OPERACION.md). No incluyas `.env`, archivos subidos ni volcados de datos en Git.

## Pruebas

Pruebas locales aisladas, con archivos y correo en memoria:

```powershell
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python manage.py test --noinput
.venv/Scripts/python manage.py check
.venv/Scripts/python manage.py makemigrations --check --dry-run
.venv/Scripts/python -m ruff check .
```

Las pruebas de navegador usan Chrome instalado en Windows; en otro entorno configura `CHROME_EXECUTABLE` con la ruta del ejecutable de Chromium. Si no existe, esas tres pruebas se marcan omitidas. Para instalar el navegador de Playwright usa `python -m playwright install chromium`. CI ejecuta PostgreSQL y Chromium.

El modo local facilita comprobaciones funcionales. La aceptación cloud requiere PostgreSQL desechable, navegador e integración con staging; consulta [ACEPTACION.md](docs/ACEPTACION.md). Nunca apuntes el runner a la base de producción: crea y destruye bases de prueba.

## Datos y documentación

Los datos territoriales iniciales proceden de GeoNames, con atribución CC BY 4.0. Su procedencia, formato y límites están en [data/README.md](data/README.md); no constituyen un catálogo administrativo oficial.

- [Plan funcional y técnico](docs/PLAN_DESARROLLO.md)
- [Prompts de desarrollo](docs/PROMPTS_DESARROLLO.md)
- [Decisiones implementadas](docs/DECISIONES.md)
- [Estado y límites actuales](docs/ESTADO_DESARROLLO.md)
- [Backlog de cierre y evolución](docs/BACKLOG.md)
- [Operación y servicios externos](docs/OPERACION.md)
- [Evidencia de aceptación](docs/ACEPTACION.md)
