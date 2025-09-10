-- Reset non-constraint indexes, realign foreign keys to domain IDs, and recreate indexes
-- This migration standardizes FKs to use entities.entity_id and properties.property_id
-- CAUTION: Requires data migration steps included below

begin;

-- 1) Drop outdated foreign keys that point to PK ids where we intend to use domain IDs
alter table if exists public.document_extraction_queue drop constraint if exists document_extraction_queue_property_id_fkey;
alter table if exists public.document_payments        drop constraint if exists document_payments_property_id_fkey;
alter table if exists public.tax_documents           drop constraint if exists tax_documents_property_id_fkey;
alter table if exists public.tax_documents           drop constraint if exists tax_documents_entity_id_fkey;

-- 2) Update data to domain IDs (property_id/entity_id) where necessary
-- document_extraction_queue.property_id: id -> property_id
update public.document_extraction_queue d
set property_id = p.property_id
from public.properties p
where d.property_id = p.id;

-- document_payments.property_id: id -> property_id
update public.document_payments dp
set property_id = p.property_id
from public.properties p
where dp.property_id = p.id;

-- tax_documents.property_id: id -> property_id; entity_id: id -> entity_id
update public.tax_documents td
set property_id = p.property_id
from public.properties p
where td.property_id = p.id;

update public.tax_documents td
set entity_id = e.entity_id
from public.entities e
where td.entity_id = e.id;

-- 3) Drop all non-constraint indexes (keeps primary keys and unique constraints)
do $$
declare rec record;
begin
  for rec in
    select i.schemaname, i.indexname
    from pg_indexes i
    left join pg_class c on c.relname = i.indexname
    left join pg_constraint con on con.conindid = c.oid
    where i.schemaname = 'public'
      and con.oid is null -- not backing a constraint (PK/UNIQUE)
  loop
    execute format('drop index if exists %I.%I', rec.schemaname, rec.indexname);
  end loop;
end$$;

-- 4) Recreate foreign keys to domain IDs
alter table public.document_extraction_queue
  add constraint document_extraction_queue_property_id_fkey
    foreign key (property_id) references public.properties(property_id) on delete cascade;

alter table public.document_payments
  add constraint document_payments_property_id_fkey
    foreign key (property_id) references public.properties(property_id) on delete cascade;

alter table public.tax_documents
  add constraint tax_documents_property_id_fkey
    foreign key (property_id) references public.properties(property_id) on delete cascade,
  add constraint tax_documents_entity_id_fkey
    foreign key (entity_id) references public.entities(entity_id) on delete set null;

-- 5) Recreate fresh supporting indexes aligned to query patterns

-- properties
create index if not exists idx_properties_parent_entity_id on public.properties(parent_entity_id);
create index if not exists idx_properties_jurisdiction on public.properties(jurisdiction);
create index if not exists idx_properties_state on public.properties(state);
create index if not exists idx_properties_property_name on public.properties(property_name);
create index if not exists idx_properties_tax_due_date on public.properties(tax_due_date) where tax_due_date is not null;
create index if not exists idx_properties_updated_at on public.properties(updated_at);

-- entities
create index if not exists idx_entities_entity_name on public.entities(entity_name);
create index if not exists idx_entities_state on public.entities(state);
create index if not exists idx_entities_jurisdiction on public.entities(jurisdiction);
create index if not exists idx_entities_entity_type on public.entities(entity_type);

-- jurisdictions
create index if not exists idx_jurisdictions_state on public.jurisdictions(state);
create index if not exists idx_jurisdictions_type on public.jurisdictions(jurisdiction_type);
create index if not exists idx_jurisdictions_active on public.jurisdictions(is_active);

-- tax_extractions
create index if not exists idx_tax_extractions_property_id on public.tax_extractions(property_id);
create index if not exists idx_tax_extractions_entity_id on public.tax_extractions(entity_id);
create index if not exists idx_tax_extractions_date on public.tax_extractions(extraction_date);
create index if not exists idx_tax_extractions_status on public.tax_extractions(extraction_status);
create index if not exists idx_tax_extractions_tax_year on public.tax_extractions(tax_year);

-- tax_documents
create index if not exists idx_tax_documents_property_id on public.tax_documents(property_id);
create index if not exists idx_tax_documents_entity_id on public.tax_documents(entity_id);
create index if not exists idx_tax_documents_due_date on public.tax_documents(due_date);
create index if not exists idx_tax_documents_status on public.tax_documents(status);
create index if not exists idx_tax_documents_document_type on public.tax_documents(document_type);
create index if not exists idx_tax_documents_search on public.tax_documents using gin(search_vector);
create index if not exists idx_tax_documents_tags on public.tax_documents using gin(tags);

-- document_extraction_queue
create index if not exists idx_deq_property_id on public.document_extraction_queue(property_id);
create index if not exists idx_deq_status on public.document_extraction_queue(status);
create index if not exists idx_deq_priority on public.document_extraction_queue(priority);

-- document_payments
create index if not exists idx_doc_pay_property_id on public.document_payments(property_id);
create index if not exists idx_doc_pay_document_id on public.document_payments(document_id);
create index if not exists idx_doc_pay_payment_date on public.document_payments(payment_date);

commit;

