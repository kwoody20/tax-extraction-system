-- Fix anonymous access to read data
-- This allows the anon role to read all data

-- Drop existing SELECT policies for anon
DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON entities;
DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON properties;
DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON tax_extractions;
DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON jurisdictions;
DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON entity_relationships;

-- Create new policies that allow both anon and authenticated users to read
CREATE POLICY "Enable read for all users" ON entities
    FOR SELECT USING (true);

CREATE POLICY "Enable read for all users" ON properties
    FOR SELECT USING (true);

CREATE POLICY "Enable read for all users" ON tax_extractions
    FOR SELECT USING (true);

CREATE POLICY "Enable read for all users" ON jurisdictions
    FOR SELECT USING (true);

CREATE POLICY "Enable read for all users" ON entity_relationships
    FOR SELECT USING (true);

-- Keep write operations restricted to authenticated users
CREATE POLICY "Enable insert for authenticated users" ON entities
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable update for authenticated users" ON entities
    FOR UPDATE USING (auth.role() = 'authenticated');

CREATE POLICY "Enable delete for authenticated users" ON entities
    FOR DELETE USING (auth.role() = 'authenticated');

CREATE POLICY "Enable insert for authenticated users" ON properties
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable update for authenticated users" ON properties
    FOR UPDATE USING (auth.role() = 'authenticated');

CREATE POLICY "Enable delete for authenticated users" ON properties
    FOR DELETE USING (auth.role() = 'authenticated');

CREATE POLICY "Enable insert for authenticated users" ON tax_extractions
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable update for authenticated users" ON tax_extractions
    FOR UPDATE USING (auth.role() = 'authenticated');

CREATE POLICY "Enable delete for authenticated users" ON tax_extractions
    FOR DELETE USING (auth.role() = 'authenticated');

-- Note: This makes all data publicly readable via the anon key
-- In production, you should use proper authentication