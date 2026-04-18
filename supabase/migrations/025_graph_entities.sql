-- ============================================================
-- GraphRAG: Entity & Relationship Tables
-- ============================================================

create extension if not exists pg_trgm;

-- 1. graph_entities — canonical entities extracted from documents
create table public.graph_entities (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  name        text not null,
  entity_type text not null,
  canonical   text,
  properties  jsonb default '{}'::jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create trigger handle_graph_entities_updated_at
  before update on public.graph_entities
  for each row execute function public.handle_updated_at();

create unique index idx_graph_entities_canonical
  on public.graph_entities(user_id, entity_type, canonical)
  where canonical is not null;

create index idx_graph_entities_user_id on public.graph_entities(user_id);
create index idx_graph_entities_type on public.graph_entities(entity_type);
create index idx_graph_entities_name on public.graph_entities using gin (name gin_trgm_ops);

-- 2. graph_relationships — edges between entities
create table public.graph_relationships (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  source_id       uuid not null references public.graph_entities(id) on delete cascade,
  target_id       uuid not null references public.graph_entities(id) on delete cascade,
  relationship    text not null,
  properties      jsonb default '{}'::jsonb,
  document_id     uuid references public.documents(id) on delete cascade,
  chunk_id        uuid references public.document_chunks(id) on delete cascade,
  created_at      timestamptz not null default now(),
  constraint no_self_loop check (source_id <> target_id)
);

create index idx_graph_rel_source on public.graph_relationships(source_id);
create index idx_graph_rel_target on public.graph_relationships(target_id);
create index idx_graph_rel_user_id on public.graph_relationships(user_id);
create index idx_graph_rel_document on public.graph_relationships(document_id);

-- 3. graph_entity_chunks — bridge: entity ↔ chunk
create table public.graph_entity_chunks (
  id          uuid primary key default gen_random_uuid(),
  entity_id   uuid not null references public.graph_entities(id) on delete cascade,
  chunk_id    uuid not null references public.document_chunks(id) on delete cascade,
  document_id uuid not null references public.documents(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  unique(entity_id, chunk_id)
);

create index idx_gec_chunk on public.graph_entity_chunks(chunk_id);
create index idx_gec_entity on public.graph_entity_chunks(entity_id);
create index idx_gec_user on public.graph_entity_chunks(user_id);

-- 4. RLS — graph_entities
alter table public.graph_entities enable row level security;

create policy "users can see own entities"
  on public.graph_entities for select using (auth.uid() = user_id);
create policy "users can create own entities"
  on public.graph_entities for insert with check (auth.uid() = user_id);
create policy "users can update own entities"
  on public.graph_entities for update using (auth.uid() = user_id);
create policy "users can delete own entities"
  on public.graph_entities for delete using (auth.uid() = user_id);

-- 5. RLS — graph_relationships
alter table public.graph_relationships enable row level security;

create policy "users can see own relationships"
  on public.graph_relationships for select using (auth.uid() = user_id);
create policy "users can create own relationships"
  on public.graph_relationships for insert with check (auth.uid() = user_id);
create policy "users can delete own relationships"
  on public.graph_relationships for delete using (auth.uid() = user_id);

-- 6. RLS — graph_entity_chunks
alter table public.graph_entity_chunks enable row level security;

create policy "users can see own entity_chunks"
  on public.graph_entity_chunks for select using (auth.uid() = user_id);
create policy "users can create own entity_chunks"
  on public.graph_entity_chunks for insert with check (auth.uid() = user_id);
create policy "users can delete own entity_chunks"
  on public.graph_entity_chunks for delete using (auth.uid() = user_id);

-- 7. RPC: fetch graph context for retrieved chunks (1-hop traversal)
create or replace function get_graph_context_for_chunks(
  p_chunk_ids uuid[],
  p_user_id   uuid,
  p_max_hops  int default 1
)
returns jsonb
language plpgsql stable
as $$
declare
  result jsonb;
begin
  with
  direct_entities as (
    select distinct ge.id, ge.name, ge.entity_type, ge.canonical, ge.properties
    from graph_entity_chunks gec
    join graph_entities ge on ge.id = gec.entity_id
    where gec.chunk_id = any(p_chunk_ids)
      and gec.user_id = p_user_id
  ),
  related_rels as (
    select gr.id, gr.source_id, gr.target_id, gr.relationship, gr.properties,
           gr.document_id
    from graph_relationships gr
    where gr.user_id = p_user_id
      and (gr.source_id in (select id from direct_entities)
           or gr.target_id in (select id from direct_entities))
  ),
  neighbor_entities as (
    select distinct ge.id, ge.name, ge.entity_type, ge.canonical, ge.properties
    from graph_entities ge
    where ge.user_id = p_user_id
      and ge.id in (
        select source_id from related_rels
        union
        select target_id from related_rels
      )
      and ge.id not in (select id from direct_entities)
  ),
  cross_doc_chunks as (
    select gec.entity_id, gec.chunk_id, gec.document_id,
           dc.content, d.filename
    from graph_entity_chunks gec
    join document_chunks dc on dc.id = gec.chunk_id
    join documents d on d.id = gec.document_id
    where gec.user_id = p_user_id
      and gec.entity_id in (select id from direct_entities)
      and gec.chunk_id <> all(p_chunk_ids)
    limit 5
  )
  select jsonb_build_object(
    'entities', coalesce((select jsonb_agg(row_to_json(de)) from direct_entities de), '[]'::jsonb),
    'relationships', coalesce((select jsonb_agg(row_to_json(rr)) from related_rels rr), '[]'::jsonb),
    'neighbor_entities', coalesce((select jsonb_agg(row_to_json(ne)) from neighbor_entities ne), '[]'::jsonb),
    'cross_document_chunks', coalesce((select jsonb_agg(row_to_json(cdc)) from cross_doc_chunks cdc), '[]'::jsonb)
  ) into result;

  return result;
end;
$$;

-- 8. System settings
alter table public.system_settings
  add column if not exists graph_enabled boolean not null default false,
  add column if not exists graph_entity_extraction_model text not null default '';

update public.system_settings
  set graph_enabled = false, graph_entity_extraction_model = ''
  where id = 1;
