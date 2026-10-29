# ResiVe — Decisiones implementadas

| Decisión | Motivo y consecuencia |
|---|---|
| Django y plantillas | Un despliegue; reutiliza formularios, permisos y admin |
| HTMX con documentos completos seleccionados por región | Enlaces directos y formularios normales; mejora la navegación sin SPA separada |
| JavaScript y CSS propios | Interacciones locales y diseño adaptable sin compilador frontend obligatorio |
| Supabase como PostgreSQL | ORM y migraciones Django; sin identidad duplicada en Supabase Auth |
| Django Auth y sesiones | Una cuenta busca y publica; permisos por objeto en backend |
| Correo normalizado y restricción por minúsculas | Evita duplicados también en PostgreSQL |
| R2 privado con firma por lectura | Borradores/retirados sin prefijos públicos; firmas ya emitidas duran hasta cinco minutos |
| Carga a través de Django | Valida y transforma antes de almacenar; carga directa se evaluará por volumen |
| Decimal y USD/VES | Sin comparación entre monedas ni conversión automática |
| Entidad → localidad → zona | No identifica ciudad con municipio; cobertura revisada por separado |
| Editor agrupado y Django Admin | Recorrido funcional con menos pantallas y sin backoffice duplicado |
| Clave de reintento y versión de visita | Evita repetir mensajes y rechaza confirmaciones de estados antiguos |
| Outbox persistente | Fallos SMTP no pierden consultas; existe posibilidad de duplicado tras aceptación |
| Compensación de archivos/SQL | Sin transacción distribuida; limpieza y reconciliación conservadora |
| Modo local explícito | Prueba sin credenciales; no representa una integración cloud comprobada |

Las claves cloud nunca pertenecen al navegador. El esquema queda fuera de la Data API; las sesiones Django no crean contexto RLS de Supabase. Los roles SQL de migración y ejecución se preparan por separado según [OPERACION.md](OPERACION.md).

El plan y los prompts conservan el diseño de referencia. [ESTADO_DESARROLLO.md](ESTADO_DESARROLLO.md) registra implementación y diferencias.
