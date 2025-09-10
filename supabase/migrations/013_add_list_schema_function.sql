-- List all tables and columns for a given schema via PostgREST RPC
-- Usage (REST): POST /rest/v1/rpc/list_schema {"p_schema": "public"}

create or replace function public.list_schema(p_schema text default 'public')
returns table(
  table_schema text,
  table_name   text,
  column_name  text,
  data_type    text,
  is_nullable  text
)
language sql
stable
security definer
as $$
  select c.table_schema,
         c.table_name,
         c.column_name,
         c.data_type,
         c.is_nullable
  from information_schema.columns c
  where c.table_schema = p_schema
  order by c.table_name, c.ordinal_position;
$$;

-- Allow execution from API roles
grant execute on function public.list_schema(text) to anon, authenticated, service_role;

