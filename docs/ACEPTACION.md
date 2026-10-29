# ResiVe — Evidencia de aceptación

Fecha: 28 de octubre de 2026. Se distinguen pruebas ejecutadas de comprobaciones pendientes; este documento no certifica preparación para producción.

## Resultados registrados

| Comprobación | Evidencia actual |
|---|---|
| Cuentas, notificaciones y smoke cloud aislado | 28 pruebas Django aprobadas con `manage.py test apps.accounts apps.notifications --noinput` en modo local |
| Verificación y recuperación | Tokens expirados/reutilizados rechazados; recuperación completa comprobada por el cliente de pruebas Django |
| Privacidad | Aislamiento de cuentas/notificaciones, CSRF, suspensión y caché privada aprobados |
| SMTP outbox | Backend en memoria: fallo, reintento, preferencia y omisión de correos ya enviados |
| Comando cloud | Dobles de prueba: guardas de entorno, objeto temporal, limpieza y errores sin secretos; no conexión real |
| Análisis estático de esos módulos | Ruff aprobado excluyendo migraciones generadas |

Integración ejecutada: **101/101 pruebas aprobadas sobre PostgreSQL 17.6 local y Chrome**, incluyendo 98 pruebas de backend y 3 recorridos de navegador. Comando: `python manage.py test --noinput` con `DATABASE_URL` de una base local desechable, `DATABASE_SCHEMA=public`, `LOCAL_DEMO=1` y `DJANGO_DEBUG=1`. El runner creó y destruyó su base de prueba. SMTP y archivos se aislaron en memoria.

También se ejecutaron las migraciones en un esquema `resive` separado con el rol `resive_migrator`; el rol `resive_runtime` pudo leer y escribir datos y recibió denegación al intentar crear tablas tanto en `resive` como en `public`. Se comprobó que `anon` no tiene USAGE sobre `resive`. Esto valida el SQL en PostgreSQL local, no los privilegios efectivos del proyecto Supabase del usuario.

`manage.py check`, `makemigrations --check --dry-run`, Ruff y `git diff --check` aprobados. `check --deploy` con configuración de producción de ejemplo dejó únicamente advertencias W005 y W021: HSTS para todos los subdominios y preload se mantienen desactivados hasta conocer el dominio y su política HTTPS. No se hicieron conexiones cloud durante ese control.

Estas comprobaciones no demuestran acceso efectivo a Supabase/R2, entrega SMTP real ni una auditoría exhaustiva de concurrencia o seguridad.

## Matriz de aceptación funcional

| Recorrido | Resultado esperado |
|---|---|
| Cuenta → correo → confirmar | Verificación por POST y enlace no reutilizable |
| Acceso → perfil → salir | Cuenta correcta, cambios persistidos, sesión cerrada y navegación actualizada |
| Anuncio → fotos → revisión | Borrador guardado; se exige correo, campos y foto válida |
| Moderador aprueba | Anuncio público con historial de actor y estado |
| Buscar por entidad/localidad | Solo disponibles, relaciones coherentes y filtros compartibles |
| Favorito y petición repetida | Un único favorito y estado consistente |
| Consulta → respuesta → visita | Hilo privado, mensajes sin duplicados y confirmación de la otra persona |
| Reprogramación | Nueva confirmación y rechazo de versión obsoleta |
| Bloqueo o denuncia | Escritura bloqueada y evidencia limitada al caso autorizado |
| Retirada o suspensión | Sin resultados públicos ni nuevas firmas públicas de sus fotos |
| Tercero intenta acceder | Sin edición de anuncios ni lectura de hilos/notificaciones ajenos |

## Navegador y calidad visual

Chrome verificó publicación con foto, envío a revisión y aprobación mediante el servicio de dominio, consulta y propuesta de visita; acceso/salida con encabezado actualizado; filtros, atrás/adelante y favoritos en móvil. Una variable mantenida en `window` permaneció intacta durante las interacciones mejoradas: no hubo recarga completa del documento. No se registraron errores JavaScript ni desbordamiento horizontal en los recorridos móvil/escritorio probados.

Un tercer recorrido con JavaScript desactivado verificó búsqueda por entidad/localidad y presupuesto, acceso y favoritos. Capturas de desarrollo: `test-results/home-desktop.png`, `test-results/e2e/mobile-search.png`, `test-results/e2e/mobile-detail.png` y `test-results/e2e/desktop-consultation.png` (ignoradas por Git; no contienen datos reales).

Comprobaciones manuales adicionales recomendadas antes del lanzamiento:

- Entrada directa, recarga, atrás/adelante y formularios sin JavaScript.
- Acceso/salida con encabezado y URL correctos.
- Errores con campos preservados y foco comprensible.
- Sesión expirada, respuestas obsoletas, fallo de red y límite 429.
- Móvil, teclado, etiquetas, contraste, avisos y galería.

No hay mediciones registradas de Core Web Vitals ni una auditoría integral de accesibilidad. Las mediciones futuras deben indicar página, datos, navegador y condiciones de red.

## Condiciones externas antes de publicar

- Supabase: TLS, esquema/grants, Data API y conexiones comprobados en staging.
- R2: bucket privado, credencial, URLs temporales, retirada y limpieza comprobados.
- SMTP: remitente autenticado y recepción real de verificación/recuperación.
- Catálogo GeoNames: relaciones y cobertura revisadas; licencia y atribución mantenidas.
- Restauración conjunta PostgreSQL/R2 ensayada con tiempos medidos.
- Soporte y textos de privacidad/condiciones revisados.
- Sin defectos críticos abiertos de permisos, exposición o pérdida de datos.

Consulta [OPERACION.md](OPERACION.md). Una comprobación simulada sigue siendo simulada hasta ejecutarse contra su entorno.

## Google OAuth

12 pruebas nuevas sobre PostgreSQL verifican creación, vinculación explícita, cuentas suspendidas, CSRF, state y cancelación, recuperación para cuentas Google, privacidad de credenciales y tokens RS256 de prueba (firma, nonce, audiencia, issuer y caducidad). No se contactó Google real. El total de 101 incluye estas pruebas.

## Navegación pública — 29 de octubre de 2026

Se corrigió la carga del selector de localidades: no incluye todo el catálogo al abrir ventas/alquileres; carga las ciudades del estado elegido y resuelve sus nombres sin una consulta adicional por localidad. Sin JavaScript se elige el estado, se busca y después se elige la ciudad. Se conservan los enlaces directos con filtros.

Comprobación local con el catálogo real: /ventas/ pasó de aproximadamente 1,1 MB y 21 segundos a 8,7 KB y 0,11 segundos en una medición HTTP. Chrome comprobó Quiero comprar, Alquilar, Comprar e Ingresar sin recargar el documento; cambios observados entre 0,12 y 0,43 segundos. Son mediciones locales, no garantías de rendimiento en producción. Se añadieron regresiones de consultas por localidad y navegación desde la portada.
