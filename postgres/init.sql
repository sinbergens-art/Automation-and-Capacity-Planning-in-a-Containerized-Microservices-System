-- Postgres init script.
-- Each microservice creates its own tables on startup,
-- so this file is intentionally minimal: it just makes
-- sure the database exists. The compose env vars do that
-- automatically; this file is here as documentation and to
-- give us a place to add any future seed data.
 
-- Example: create read-only user (commented out, optional)
-- CREATE USER readonly WITH PASSWORD 'readonly';
-- GRANT CONNECT ON DATABASE appdb TO readonly;
-- GRANT USAGE ON SCHEMA public TO readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;
 
SELECT 'Postgres ready for SRE Shop' AS notice;
 