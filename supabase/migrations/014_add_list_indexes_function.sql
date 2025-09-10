-- List indexes and their definitions via PostgREST RPC
-- Usage (REST): POST /rest/v1/rpc/list_indexes {"p_schema": "public"}

create or replace function public.list_indexes(p_schema text default 'public')
returns table(
  schemaname text,
  tablename  text,
  indexname  text,
  indexdef   text
)
language sql
stable
security definer
as $$
  select i.schemaname, i.tablename, i.indexname, i.indexdef
  from pg_indexes i
  where i.schemaname = p_schema
  order by i.tablename, i.indexname;
$$;

grant execute on function public.list_indexes(text) to anon, authenticated, service_role;

