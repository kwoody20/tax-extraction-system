-- List foreign keys and their referenced columns via PostgREST RPC
-- Usage (REST): POST /rest/v1/rpc/list_foreign_keys {"p_schema": "public"}

create or replace function public.list_foreign_keys(p_schema text default 'public')
returns table(
  constraint_name text,
  table_schema     text,
  table_name       text,
  column_name      text,
  foreign_schema   text,
  foreign_table    text,
  foreign_column   text
)
language sql
stable
security definer
as $$
  select
    tc.constraint_name,
    tc.table_schema,
    tc.table_name,
    kcu.column_name,
    ccu.table_schema as foreign_schema,
    ccu.table_name   as foreign_table,
    ccu.column_name  as foreign_column
  from information_schema.table_constraints tc
  join information_schema.key_column_usage kcu
    on tc.constraint_name = kcu.constraint_name
   and tc.table_schema   = kcu.table_schema
  join information_schema.constraint_column_usage ccu
    on ccu.constraint_name = tc.constraint_name
   and ccu.table_schema    = tc.table_schema
  where tc.constraint_type = 'FOREIGN KEY'
    and tc.table_schema = p_schema
  order by tc.table_name, kcu.ordinal_position;
$$;

grant execute on function public.list_foreign_keys(text) to anon, authenticated, service_role;

