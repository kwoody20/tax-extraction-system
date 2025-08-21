-- Temporarily disable RLS for data import
-- Run this before importing data, then re-enable after

-- Option 1: Disable RLS temporarily (run this first)
ALTER TABLE entities DISABLE ROW LEVEL SECURITY;
ALTER TABLE properties DISABLE ROW LEVEL SECURITY;
ALTER TABLE tax_extractions DISABLE ROW LEVEL SECURITY;
ALTER TABLE jurisdictions DISABLE ROW LEVEL SECURITY;
ALTER TABLE entity_relationships DISABLE ROW LEVEL SECURITY;

-- Option 2: Or create permissive policies for anon role (alternative approach)
-- This allows anon users to insert data temporarily

-- Drop existing policies first
DROP POLICY IF EXISTS "Enable insert for authenticated users" ON entities;
DROP POLICY IF EXISTS "Enable insert for authenticated users" ON properties;

-- Create permissive insert policies for anon role
CREATE POLICY "Allow anon inserts temporarily" ON entities
    FOR INSERT TO anon
    WITH CHECK (true);

CREATE POLICY "Allow anon inserts temporarily" ON properties
    FOR INSERT TO anon
    WITH CHECK (true);

-- Also allow anon to update (for upsert operations)
CREATE POLICY "Allow anon updates temporarily" ON entities
    FOR UPDATE TO anon
    USING (true);

CREATE POLICY "Allow anon updates temporarily" ON properties
    FOR UPDATE TO anon
    USING (true);

-- Grant necessary permissions to anon
GRANT INSERT, UPDATE ON entities TO anon;
GRANT INSERT, UPDATE ON properties TO anon;
GRANT INSERT, UPDATE ON tax_extractions TO anon;
GRANT INSERT, UPDATE ON jurisdictions TO anon;
GRANT INSERT, UPDATE ON entity_relationships TO anon;

-- After import is complete, run 010_restore_rls.sql to restore security