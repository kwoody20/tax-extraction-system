-- ============================================================
-- RE-ENABLE ROW LEVEL SECURITY (RLS) ON TAX SYSTEM TABLES
-- ============================================================
-- This script re-enables RLS and creates basic security policies
-- ============================================================

-- Enable RLS on all main tables
ALTER TABLE IF EXISTS public.tax_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.tax_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.document_extraction_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.document_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.entity_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.jurisdictions ENABLE ROW LEVEL SECURITY;

-- Create basic policies for authenticated users
-- These are permissive policies that allow authenticated users to perform operations

-- Policies for tax_documents table
CREATE POLICY "Enable read access for authenticated users" ON public.tax_documents
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Enable insert for authenticated users" ON public.tax_documents
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable update for authenticated users" ON public.tax_documents
    FOR UPDATE USING (auth.role() = 'authenticated');

CREATE POLICY "Enable delete for authenticated users" ON public.tax_documents
    FOR DELETE USING (auth.role() = 'authenticated');

-- Policies for properties table
CREATE POLICY "Enable read access for authenticated users" ON public.properties
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Enable insert for authenticated users" ON public.properties
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable update for authenticated users" ON public.properties
    FOR UPDATE USING (auth.role() = 'authenticated');

CREATE POLICY "Enable delete for authenticated users" ON public.properties
    FOR DELETE USING (auth.role() = 'authenticated');

-- Policies for entities table
CREATE POLICY "Enable read access for authenticated users" ON public.entities
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Enable insert for authenticated users" ON public.entities
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable update for authenticated users" ON public.entities
    FOR UPDATE USING (auth.role() = 'authenticated');

CREATE POLICY "Enable delete for authenticated users" ON public.entities
    FOR DELETE USING (auth.role() = 'authenticated');

-- Optional: Add policies for anonymous/public read access
-- Uncomment these if you want public read access to certain tables

-- CREATE POLICY "Enable public read access" ON public.properties
--     FOR SELECT USING (true);

-- CREATE POLICY "Enable public read access" ON public.entities
--     FOR SELECT USING (true);

-- Optional: Service role bypass (service role can bypass RLS)
-- This is typically already configured but included for completeness
ALTER TABLE public.tax_documents FORCE ROW LEVEL SECURITY;
ALTER TABLE public.properties FORCE ROW LEVEL SECURITY;
ALTER TABLE public.entities FORCE ROW LEVEL SECURITY;

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

-- Show all policies created
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    CASE 
        WHEN cmd = 'SELECT' THEN 'READ'
        WHEN cmd = 'INSERT' THEN 'CREATE'
        WHEN cmd = 'UPDATE' THEN 'MODIFY'
        WHEN cmd = 'DELETE' THEN 'REMOVE'
        ELSE cmd
    END as operation
FROM pg_policies
WHERE schemaname = 'public'
AND tablename IN ('tax_documents', 'properties', 'entities')
ORDER BY tablename, cmd;