-- Enable Row Level Security on all tables
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE jurisdictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_relationships ENABLE ROW LEVEL SECURITY;

-- Create policies for authenticated users (adjust based on your auth requirements)

-- Entities policies
CREATE POLICY "Enable read access for all authenticated users" ON entities
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Enable insert for authenticated users" ON entities
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable update for authenticated users" ON entities
    FOR UPDATE USING (auth.role() = 'authenticated');

CREATE POLICY "Enable delete for authenticated users" ON entities
    FOR DELETE USING (auth.role() = 'authenticated');

-- Properties policies
CREATE POLICY "Enable read access for all authenticated users" ON properties
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Enable insert for authenticated users" ON properties
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable update for authenticated users" ON properties
    FOR UPDATE USING (auth.role() = 'authenticated');

CREATE POLICY "Enable delete for authenticated users" ON properties
    FOR DELETE USING (auth.role() = 'authenticated');

-- Tax extractions policies
CREATE POLICY "Enable read access for all authenticated users" ON tax_extractions
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Enable insert for authenticated users" ON tax_extractions
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable update for authenticated users" ON tax_extractions
    FOR UPDATE USING (auth.role() = 'authenticated');

CREATE POLICY "Enable delete for authenticated users" ON tax_extractions
    FOR DELETE USING (auth.role() = 'authenticated');

-- Jurisdictions policies (read-only for most users)
CREATE POLICY "Enable read access for all authenticated users" ON jurisdictions
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Enable all operations for service role" ON jurisdictions
    FOR ALL USING (auth.role() = 'service_role');

-- Entity relationships policies
CREATE POLICY "Enable read access for all authenticated users" ON entity_relationships
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Enable insert for authenticated users" ON entity_relationships
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable update for authenticated users" ON entity_relationships
    FOR UPDATE USING (auth.role() = 'authenticated');

CREATE POLICY "Enable delete for authenticated users" ON entity_relationships
    FOR DELETE USING (auth.role() = 'authenticated');

-- Grant permissions to authenticated users
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO authenticated;

-- Grant permissions to service role (for backend operations)
GRANT ALL ON SCHEMA public TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO service_role;

-- Grant permissions to anon role (for public read access if needed)
GRANT USAGE ON SCHEMA public TO anon;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;

-- Add comment
COMMENT ON SCHEMA public IS 'Property tax extraction system database schema with RLS enabled';