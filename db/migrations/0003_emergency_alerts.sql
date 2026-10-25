-- Operator alerts raised when a supervisor confirms an emergency notification.
create table if not exists emergency_alerts (
  id              uuid primary key default gen_random_uuid(),
  conversation_id uuid,
  message_id      uuid,
  question        text not null,
  location        text,
  status          text not null default 'open' check (status in ('open', 'acknowledged')),
  created_at      timestamptz not null default now(),
  acknowledged_at timestamptz
);

-- One alert per assistant message (makes notify idempotent).
create unique index if not exists emergency_alerts_message_uq
  on emergency_alerts (message_id) where message_id is not null;
create index if not exists emergency_alerts_status_idx
  on emergency_alerts (status, created_at desc);
