-- Structured facts extracted during ingestion, for counting / aggregate questions.
create schema if not exists analytics;

create table if not exists analytics.sites (
  id   serial primary key,
  name text not null unique
);

create table if not exists analytics.lines (
  id      serial primary key,
  site_id int not null references analytics.sites(id) on delete cascade,
  name    text not null,
  unique (site_id, name)
);

create table if not exists analytics.equipment (
  id          serial primary key,
  tag         text not null unique,          -- e.g. P-101, CNV-3
  name        text,
  type        text,                          -- pump, conveyor, press, compressor...
  line_id     int references analytics.lines(id) on delete set null,
  criticality text check (criticality in ('low', 'medium', 'high'))
);

create table if not exists analytics.procedures (
  id              serial primary key,
  document_id     uuid not null references public.documents(id) on delete cascade,
  source          text not null,
  title           text not null,
  equipment_id    int references analytics.equipment(id) on delete set null,
  step_count      int,
  requires_loto   boolean not null default false,
  requires_permit boolean not null default false,
  permit_type     text,
  hazard_level    text check (hazard_level in ('low', 'medium', 'high')),
  est_minutes     int,
  source_chunk_id uuid,
  unique (document_id, title)
);

create table if not exists analytics.procedure_steps (
  procedure_id    int not null references analytics.procedures(id) on delete cascade,
  step_no         int not null,
  action_type     text,                      -- isolate, verify, inspect, replace, energize...
  text            text not null,
  is_prerequisite boolean not null default false,
  primary key (procedure_id, step_no)
);

create table if not exists analytics.ppe_requirements (
  procedure_id int not null references analytics.procedures(id) on delete cascade,
  ppe_item     text not null,
  primary key (procedure_id, ppe_item)
);

create table if not exists analytics.pm_tasks (
  id              serial primary key,
  equipment_id    int not null references analytics.equipment(id) on delete cascade,
  task            text not null,
  interval_days   int,
  est_minutes     int,
  parts           text[] not null default '{}',
  source_chunk_id uuid,
  unique (equipment_id, task)
);

create table if not exists analytics.quality_specs (
  id              serial primary key,
  part            text not null,
  characteristic  text not null,
  nominal         numeric,
  lsl             numeric,
  usl             numeric,
  unit            text,
  aql             numeric,
  inspection_freq text,
  source_chunk_id uuid,
  unique (part, characteristic)
);

-- Read-only role for the text-to-SQL path.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'analytics_reader') then
    create role analytics_reader login password 'analytics_reader';
  end if;
end $$;

grant usage on schema analytics to analytics_reader;
grant select on all tables in schema analytics to analytics_reader;
alter default privileges in schema analytics grant select on tables to analytics_reader;
alter role analytics_reader set statement_timeout = '5s';
alter role analytics_reader set search_path = analytics;
