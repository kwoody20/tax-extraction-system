-- ============================================================
-- DISABLE ROW LEVEL SECURITY (RLS) ON TAX SYSTEM TABLES
-- ============================================================
-- WARNING: This removes all row-level security policies.
-- Only use in development or if you understand the security implications.
-- ============================================================

-- Disable RLS on main tables
ALTER TABLE IF EXISTS public.tax_documents DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.properties DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.entities DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.tax_extractions DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.document_extraction_queue DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.document_payments DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.entity_relationships DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.jurisdictions DISABLE ROW LEVEL SECURITY;

-- Drop all existing policies (optional - for complete removal)
-- This removes the policies but keeps RLS framework in place
DO $$ 
DECLARE
    pol RECORD;
BEGIN
    -- Drop policies on tax_documents
    FOR pol IN SELECT policyname FROM pg_policies WHERE tablename = 'tax_documents' AND schemaname = 'public'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.tax_documents', pol.policyname);
    END LOOP;
    
    -- Drop policies on properties
    FOR pol IN SELECT policyname FROM pg_policies WHERE tablename = 'properties' AND schemaname = 'public'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.properties', pol.policyname);
    END LOOP;
    
    -- Drop policies on entities
    FOR pol IN SELECT policyname FROM pg_policies WHERE tablename = 'entities' AND schemaname = 'public'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.entities', pol.policyname);
    END LOOP;
END $$;

-- Grant full permissions to authenticated and anon users
GRANT ALL ON public.tax_documents TO authenticated;
GRANT ALL ON public.tax_documents TO anon;
GRANT ALL ON public.properties TO authenticated;
GRANT ALL ON public.properties TO anon;
GRANT ALL ON public.entities TO authenticated;
GRANT ALL ON public.entities TO anon;

-- Grant permissions to service role (if needed)
GRANT ALL ON public.tax_documents TO service_role;
GRANT ALL ON public.properties TO service_role;
GRANT ALL ON public.entities TO service_role;

-- Verify RLS status
SELECT 
    schemaname,
    tablename,
    rowsecurity,
    CASE 
        WHEN rowsecurity = true THEN 'ENABLED'
        ELSE 'DISABLED'
    END as rls_status
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('tax_documents', 'properties', 'entities', 'tax_extractions', 'jurisdictions')
ORDER BY tablename;

-- Show any remaining policies
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies
WHERE schemaname = 'public'
AND tablename IN ('tax_documents', 'properties', 'entities')
ORDER BY tablename, policyname;