-- Performance optimization functions for api_public_enhanced.py
-- These are OPTIONAL - the API works without them but performs better with them

-- Function: Get aggregated tax statistics
CREATE OR REPLACE FUNCTION get_tax_statistics()
RETURNS TABLE (
    total_properties BIGINT,
    total_entities BIGINT,
    total_outstanding NUMERIC,
    total_previous NUMERIC,
    extracted_count BIGINT,
    pending_count BIGINT,
    last_extraction_date TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(DISTINCT p.id)::BIGINT as total_properties,
        COUNT(DISTINCT e.entity_id)::BIGINT as total_entities,
        COALESCE(SUM(p.amount_due), 0)::NUMERIC as total_outstanding,
        COALESCE(SUM(p.previous_year_taxes), 0)::NUMERIC as total_previous,
        COUNT(DISTINCT CASE WHEN p.amount_due > 0 THEN p.id END)::BIGINT as extracted_count,
        COUNT(DISTINCT CASE WHEN (p.amount_due IS NULL OR p.amount_due = 0) THEN p.id END)::BIGINT as pending_count,
        MAX(p.updated_at) as last_extraction_date
    FROM properties p
    LEFT JOIN entities e ON p.entity_id = e.entity_id;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function: Get extraction counts
CREATE OR REPLACE FUNCTION get_extraction_counts()
RETURNS TABLE (
    total BIGINT,
    extracted BIGINT,
    pending BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as total,
        COUNT(CASE WHEN amount_due > 0 THEN 1 END)::BIGINT as extracted,
        COUNT(CASE WHEN amount_due IS NULL OR amount_due = 0 THEN 1 END)::BIGINT as pending
    FROM properties;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function: Get jurisdiction statistics
CREATE OR REPLACE FUNCTION get_jurisdiction_stats()
RETURNS TABLE (
    jurisdiction TEXT,
    count BIGINT,
    extracted_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.jurisdiction,
        COUNT(*)::BIGINT as count,
        COUNT(CASE WHEN p.amount_due > 0 THEN 1 END)::BIGINT as extracted_count
    FROM properties p
    WHERE p.jurisdiction IS NOT NULL
    GROUP BY p.jurisdiction
    ORDER BY count DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function: Get properties with pagination metadata
CREATE OR REPLACE FUNCTION get_properties_paginated(
    p_limit INTEGER DEFAULT 100,
    p_offset INTEGER DEFAULT 0,
    p_jurisdiction TEXT DEFAULT NULL,
    p_state TEXT DEFAULT NULL,
    p_entity_id UUID DEFAULT NULL
)
RETURNS TABLE (
    properties JSONB,
    total_count BIGINT,
    has_more BOOLEAN
) AS $$
DECLARE
    v_properties JSONB;
    v_total BIGINT;
    v_has_more BOOLEAN;
BEGIN
    -- Get filtered count
    SELECT COUNT(*) INTO v_total
    FROM properties p
    WHERE (p_jurisdiction IS NULL OR p.jurisdiction = p_jurisdiction)
      AND (p_state IS NULL OR p.state = p_state)
      AND (p_entity_id IS NULL OR p.entity_id = p_entity_id);
    
    -- Get paginated results
    SELECT jsonb_agg(row_to_json(p.*))
    INTO v_properties
    FROM (
        SELECT *
        FROM properties
        WHERE (p_jurisdiction IS NULL OR jurisdiction = p_jurisdiction)
          AND (p_state IS NULL OR state = p_state)
          AND (p_entity_id IS NULL OR entity_id = p_entity_id)
        ORDER BY id
        LIMIT p_limit
        OFFSET p_offset
    ) p;
    
    -- Check if there are more results
    v_has_more := (p_offset + p_limit) < v_total;
    
    RETURN QUERY SELECT v_properties, v_total, v_has_more;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function: Get extraction trends
CREATE OR REPLACE FUNCTION get_extraction_trends(
    p_days INTEGER DEFAULT 30,
    p_jurisdiction TEXT DEFAULT NULL
)
RETURNS TABLE (
    date DATE,
    success_count BIGINT,
    failed_count BIGINT,
    total_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        DATE(te.extraction_date) as date,
        COUNT(CASE WHEN te.extraction_status = 'success' THEN 1 END)::BIGINT as success_count,
        COUNT(CASE WHEN te.extraction_status != 'success' THEN 1 END)::BIGINT as failed_count,
        COUNT(*)::BIGINT as total_count
    FROM tax_extractions te
    LEFT JOIN properties p ON te.property_id = p.id
    WHERE te.extraction_date >= CURRENT_DATE - INTERVAL '1 day' * p_days
      AND (p_jurisdiction IS NULL OR p.jurisdiction = p_jurisdiction)
    GROUP BY DATE(te.extraction_date)
    ORDER BY date DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Index optimizations for better query performance
CREATE INDEX IF NOT EXISTS idx_properties_jurisdiction ON properties(jurisdiction) WHERE jurisdiction IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_properties_state ON properties(state) WHERE state IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_properties_entity_id ON properties(entity_id) WHERE entity_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_properties_amount_due ON properties(amount_due);
CREATE INDEX IF NOT EXISTS idx_properties_due_date ON properties(due_date) WHERE due_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_properties_updated_at ON properties(updated_at);

-- Index for tax_extractions if table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tax_extractions') THEN
        CREATE INDEX IF NOT EXISTS idx_tax_extractions_property_id ON tax_extractions(property_id);
        CREATE INDEX IF NOT EXISTS idx_tax_extractions_date ON tax_extractions(extraction_date);
        CREATE INDEX IF NOT EXISTS idx_tax_extractions_status ON tax_extractions(extraction_status);
    END IF;
END $$;

-- Create materialized view for faster statistics (optional)
-- This can be refreshed periodically for even better performance
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_property_statistics AS
SELECT 
    COUNT(DISTINCT p.id) as total_properties,
    COUNT(DISTINCT e.entity_id) as total_entities,
    COALESCE(SUM(p.amount_due), 0) as total_outstanding,
    COALESCE(SUM(p.previous_year_taxes), 0) as total_previous,
    COUNT(DISTINCT CASE WHEN p.amount_due > 0 THEN p.id END) as extracted_count,
    COUNT(DISTINCT CASE WHEN (p.amount_due IS NULL OR p.amount_due = 0) THEN p.id END) as pending_count,
    MAX(p.updated_at) as last_extraction_date,
    CURRENT_TIMESTAMP as refreshed_at
FROM properties p
LEFT JOIN entities e ON p.entity_id = e.entity_id;

-- Create index on materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_property_statistics_refresh ON mv_property_statistics(refreshed_at);

-- Function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_property_statistics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_property_statistics;
END;
$$ LANGUAGE plpgsql;

-- Grant appropriate permissions
GRANT EXECUTE ON FUNCTION get_tax_statistics() TO authenticated;
GRANT EXECUTE ON FUNCTION get_extraction_counts() TO authenticated;
GRANT EXECUTE ON FUNCTION get_jurisdiction_stats() TO authenticated;
GRANT EXECUTE ON FUNCTION get_properties_paginated(INTEGER, INTEGER, TEXT, TEXT, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION get_extraction_trends(INTEGER, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION refresh_property_statistics() TO authenticated;
GRANT SELECT ON mv_property_statistics TO authenticated;