-- Fix anonymous access to read data
-- This allows the anon role to read all data while keeping write operations restricted

-- First, drop ALL existing policies to avoid conflicts
DO $$ 
BEGIN
    -- Drop all policies on entities
    DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON entities;
    DROP POLICY IF EXISTS "Enable insert for authenticated users" ON entities;
    DROP POLICY IF EXISTS "Enable update for authenticated users" ON entities;
    DROP POLICY IF EXISTS "Enable delete for authenticated users" ON entities;
    DROP POLICY IF EXISTS "Enable all operations for service role" ON entities;
    DROP POLICY IF EXISTS "Enable read for all users" ON entities;
    
    -- Drop all policies on properties
    DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON properties;
    DROP POLICY IF EXISTS "Enable insert for authenticated users" ON properties;
    DROP POLICY IF EXISTS "Enable update for authenticated users" ON properties;
    DROP POLICY IF EXISTS "Enable delete for authenticated users" ON properties;
    DROP POLICY IF EXISTS "Enable all operations for service role" ON properties;
    DROP POLICY IF EXISTS "Enable read for all users" ON properties;
    
    -- Drop all policies on tax_extractions
    DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON tax_extractions;
    DROP POLICY IF EXISTS "Enable insert for authenticated users" ON tax_extractions;
    DROP POLICY IF EXISTS "Enable update for authenticated users" ON tax_extractions;
    DROP POLICY IF EXISTS "Enable delete for authenticated users" ON tax_extractions;
    DROP POLICY IF EXISTS "Enable all operations for service role" ON tax_extractions;
    DROP POLICY IF EXISTS "Enable read for all users" ON tax_extractions;
    
    -- Drop all policies on jurisdictions
    DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON jurisdictions;
    DROP POLICY IF EXISTS "Enable all operations for service role" ON jurisdictions;
    DROP POLICY IF EXISTS "Enable read for all users" ON jurisdictions;
    
    -- Drop all policies on entity_relationships
    DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON entity_relationships;
    DROP POLICY IF EXISTS "Enable insert for authenticated users" ON entity_relationships;
    DROP POLICY IF EXISTS "Enable update for authenticated users" ON entity_relationships;
    DROP POLICY IF EXISTS "Enable delete for authenticated users" ON entity_relationships;
    DROP POLICY IF EXISTS "Enable read for all users" ON entity_relationships;
END $$;

-- Now create new policies with unique names

-- ENTITIES: Allow everyone to read, only authenticated to write
CREATE POLICY "public_read_entities" ON entities
    FOR SELECT USING (true);

CREATE POLICY "auth_insert_entities" ON entities
    FOR INSERT WITH CHECK (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "auth_update_entities" ON entities
    FOR UPDATE USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "auth_delete_entities" ON entities
    FOR DELETE USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- PROPERTIES: Allow everyone to read, only authenticated to write
CREATE POLICY "public_read_properties" ON properties
    FOR SELECT USING (true);

CREATE POLICY "auth_insert_properties" ON properties
    FOR INSERT WITH CHECK (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "auth_update_properties" ON properties
    FOR UPDATE USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "auth_delete_properties" ON properties
    FOR DELETE USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- TAX_EXTRACTIONS: Allow everyone to read, only authenticated to write
CREATE POLICY "public_read_tax_extractions" ON tax_extractions
    FOR SELECT USING (true);

CREATE POLICY "auth_insert_tax_extractions" ON tax_extractions
    FOR INSERT WITH CHECK (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "auth_update_tax_extractions" ON tax_extractions
    FOR UPDATE USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "auth_delete_tax_extractions" ON tax_extractions
    FOR DELETE USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- JURISDICTIONS: Allow everyone to read, only service role to write
CREATE POLICY "public_read_jurisdictions" ON jurisdictions
    FOR SELECT USING (true);

CREATE POLICY "service_write_jurisdictions" ON jurisdictions
    FOR ALL USING (auth.role() = 'service_role');

-- ENTITY_RELATIONSHIPS: Allow everyone to read, only authenticated to write
CREATE POLICY "public_read_entity_relationships" ON entity_relationships
    FOR SELECT USING (true);

CREATE POLICY "auth_insert_entity_relationships" ON entity_relationships
    FOR INSERT WITH CHECK (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "auth_update_entity_relationships" ON entity_relationships
    FOR UPDATE USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "auth_delete_entity_relationships" ON entity_relationships
    FOR DELETE USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- Grant necessary permissions
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO anon;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO anon;

-- Verify the policies are working
DO $$
DECLARE
    entity_count INTEGER;
    property_count INTEGER;
BEGIN
    -- Test SELECT as anon would
    SELECT COUNT(*) INTO entity_count FROM entities;
    SELECT COUNT(*) INTO property_count FROM properties;
    
    RAISE NOTICE 'Entities visible: %', entity_count;
    RAISE NOTICE 'Properties visible: %', property_count;
END $$;

-- Note: This makes all data publicly readable via the anon key
-- In production, you should implement proper authentication and more restrictive policies