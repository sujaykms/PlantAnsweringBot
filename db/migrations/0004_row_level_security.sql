-- Hosted Postgres (Supabase) exposes `public` tables over its REST API unless RLS is on.
-- Enable RLS with no policies = deny for anon/authenticated. The backend connects as the table
-- owner (postgres), which bypasses RLS, so the app is unaffected.
alter table documents          enable row level security;
alter table chunks             enable row level security;
alter table chunks_safety      enable row level security;
alter table chunks_maintenance enable row level security;
alter table chunks_quality     enable row level security;
alter table conversations      enable row level security;
alter table messages           enable row level security;
alter table feedback           enable row level security;
alter table emergency_alerts   enable row level security;
alter table schema_migrations  enable row level security;
