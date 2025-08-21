-- Restore RLS after data import

-- Re-enable RLS on all tables
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE jurisdictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_relationships ENABLE ROW LEVEL SECURITY;

-- Drop temporary permissive policies
DROP POLICY IF EXISTS "Allow anon inserts temporarily" ON entities;
DROP POLICY IF EXISTS "Allow anon inserts temporarily" ON properties;
DROP POLICY IF EXISTS "Allow anon updates temporarily" ON entities;
DROP POLICY IF EXISTS "Allow anon updates temporarily" ON properties;

-- Restore original policies for authenticated users
CREATE POLICY "Enable insert for authenticated users" ON entities
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable insert for authenticated users" ON properties
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

-- Revoke temporary permissions from anon
REVOKE INSERT, UPDATE ON entities FROM anon;
REVOKE INSERT, UPDATE ON properties FROM anon;
REVOKE INSERT, UPDATE ON tax_extractions FROM anon;
REVOKE INSERT, UPDATE ON jurisdictions FROM anon;
REVOKE INSERT, UPDATE ON entity_relationships FROM anon;

-- Keep read permissions for anon
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;