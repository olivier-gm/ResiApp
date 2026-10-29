-- Ejecutar como administrador del proyecto Supabase dedicado.
-- Sustituir los dos placeholders por contraseñas distintas antes de ejecutar.
-- No guardar el archivo con secretos reales ni usar el rol postgres en Django.
CREATE ROLE resive_migrator LOGIN PASSWORD 'REPLACE_MIGRATOR_PASSWORD' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE resive_runtime LOGIN PASSWORD 'REPLACE_RUNTIME_PASSWORD' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE SCHEMA resive AUTHORIZATION resive_migrator;
GRANT CONNECT ON DATABASE postgres TO resive_migrator, resive_runtime;
GRANT USAGE ON SCHEMA resive TO resive_runtime;
ALTER ROLE resive_migrator SET search_path = resive, public;
ALTER ROLE resive_runtime SET search_path = resive, public;
ALTER DEFAULT PRIVILEGES FOR ROLE resive_migrator IN SCHEMA resive
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO resive_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE resive_migrator IN SCHEMA resive
    GRANT USAGE, SELECT ON SEQUENCES TO resive_runtime;
REVOKE ALL ON SCHEMA resive FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA resive FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA resive FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE resive_migrator IN SCHEMA resive
    REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE resive_migrator IN SCHEMA resive
    REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE resive_migrator IN SCHEMA resive
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon, authenticated;
-- En Dashboard/API: desactivar Data API en el proyecto dedicado o comprobar
-- que resive NO figura entre los esquemas expuestos. No alterar esquemas auth/storage.
-- Tras migrar, comprobar que runtime no puede CREATE TABLE y sí usar nuevas tablas.
