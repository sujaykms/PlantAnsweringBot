-- Retrieval + app data. Supabase-compatible.
create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists documents (
  id          uuid primary key default gen_random_uuid(),
  source      text not null check (source in ('safety', 'maintenance', 'quality')),
  title       text not null,
  path        text not null unique,
  sha256      text not null,
  ingested_at timestamptz not null default now()
);

-- One logical table, three physical indexes (one partition per source).
create table if not exists chunks (
  id            uuid not null default gen_random_uuid(),
  document_id   uuid not null references documents(id) on delete cascade,
  source        text not null,
  section_path  text not null,
  page          int,
  doc_type      text,
  equipment_ids text[] not null default '{}',
  content       text not null,
  embed_text    text not null,
  embedding     vector(384) not null,
  tsv           tsvector generated always as (to_tsvector('english', embed_text)) stored,
  primary key (id, source)
) partition by list (source);

create table if not exists chunks_safety      partition of chunks for values in ('safety');
create table if not exists chunks_maintenance partition of chunks for values in ('maintenance');
create table if not exists chunks_quality     partition of chunks for values in ('quality');

-- Indexes declared on the parent propagate to each partition.
create index if not exists chunks_embedding_hnsw on chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_tsv_gin        on chunks using gin (tsv);
create index if not exists chunks_equipment_gin  on chunks using gin (equipment_ids);
create index if not exists chunks_document_idx   on chunks (document_id);

-- Hybrid search: vector top-N + keyword top-N fused by reciprocal rank (k=60),
-- with a small boost for chunks tagged with equipment named in the question.
create or replace function hybrid_search(
  q_emb      vector(384),
  q_text     text,
  sources    text[],
  k          int default 6,
  equipment  text[] default '{}',
  candidates int default 20
)
returns table (
  id uuid, document_id uuid, source text, title text, section_path text,
  page int, content text, score double precision
)
language sql stable
as $$
  with vec as (
    select c.id, row_number() over (order by c.embedding <=> q_emb) as rnk
    from chunks c
    where c.source = any(sources)
    order by c.embedding <=> q_emb
    limit candidates
  ),
  kw as (
    select c.id, row_number() over (order by ts_rank_cd(c.tsv, q) desc) as rnk
    from chunks c, websearch_to_tsquery('english', q_text) q
    where c.source = any(sources) and c.tsv @@ q
    order by ts_rank_cd(c.tsv, q) desc
    limit candidates
  ),
  fused as (
    select coalesce(vec.id, kw.id) as id,
           coalesce(1.0 / (60 + vec.rnk), 0) + coalesce(1.0 / (60 + kw.rnk), 0) as rrf
    from vec full outer join kw on vec.id = kw.id
  )
  select c.id, c.document_id, c.source, d.title, c.section_path, c.page, c.content,
         f.rrf + case when c.equipment_ids && equipment then 0.01 else 0 end as score
  from fused f
  join chunks c on c.id = f.id
  join documents d on d.id = c.document_id
  order by score desc
  limit k
$$;

-- App data (no users: auth is out of scope for V1).
create table if not exists conversations (
  id         uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now()
);

create table if not exists messages (
  id              uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations(id) on delete cascade,
  role            text not null check (role in ('user', 'assistant')),
  content         text not null,
  route           jsonb,
  cited_chunk_ids uuid[] not null default '{}',
  sql_query       text,
  created_at      timestamptz not null default now()
);
create index if not exists messages_conversation_idx on messages (conversation_id, created_at);

create table if not exists feedback (
  id         uuid primary key default gen_random_uuid(),
  message_id uuid not null references messages(id) on delete cascade,
  rating     smallint not null check (rating in (-1, 1)),
  comment    text,
  created_at timestamptz not null default now()
);
