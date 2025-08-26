-- Optimized Database Functions and Views for Tax Extraction System
-- These functions enable efficient querying with aggregations and joins
-- Run this migration in Supabase SQL Editor

-- ============================================
-- 1. Function for aggregated statistics
-- ============================================
CREATE OR REPLACE FUNCTION get_tax_statistics()
RETURNS TABLE (
    total_properties BIGINT,
    total_entities BIGINT,
    total_outstanding NUMERIC,
    total_previous NUMERIC,
    extracted_count BIGINT,
    pending_count BIGINT,
    last_extraction_date TIMESTAMP
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(DISTINCT p.id) as total_properties,
        COUNT(DISTINCT e.entity_id) as total_entities,
        COALESCE(SUM(p.amount_due), 0) as total_outstanding,
        COALESCE(SUM(p.previous_year_taxes), 0) as total_previous,
        COUNT(DISTINCT CASE WHEN p.amount_due > 0 THEN p.id END) as extracted_count,
        COUNT(DISTINCT CASE WHEN (p.amount_due IS NULL OR p.amount_due = 0) THEN p.id END) as pending_count,
        MAX(p.updated_at) as last_extraction_date
    FROM properties p
    LEFT JOIN entities e ON p.entity_id = e.entity_id;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION get_tax_statistics() TO anon, authenticated;

-- ============================================
-- 2. Function for extraction counts
-- ============================================
CREATE OR REPLACE FUNCTION get_extraction_counts()
RETURNS TABLE (
    total BIGINT,
    extracted BIGINT,
    pending BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN amount_due > 0 THEN 1 END) as extracted,
        COUNT(CASE WHEN amount_due IS NULL OR amount_due = 0 THEN 1 END) as pending
    FROM properties;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION get_extraction_counts() TO anon, authenticated;

-- ============================================
-- 3. Function for jurisdiction statistics
-- ============================================
CREATE OR REPLACE FUNCTION get_jurisdiction_stats()
RETURNS TABLE (
    jurisdiction TEXT,
    count BIGINT,
    extracted_count BIGINT,
    avg_tax_amount NUMERIC,
    total_tax_amount NUMERIC
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.jurisdiction,
        COUNT(*) as count,
        COUNT(CASE WHEN p.amount_due > 0 THEN 1 END) as extracted_count,
        AVG(p.amount_due) FILTER (WHERE p.amount_due > 0) as avg_tax_amount,
        SUM(p.amount_due) FILTER (WHERE p.amount_due > 0) as total_tax_amount
    FROM properties p
    WHERE p.jurisdiction IS NOT NULL
    GROUP BY p.jurisdiction
    ORDER BY count DESC;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION get_jurisdiction_stats() TO anon, authenticated;

-- ============================================
-- 4. Function for entity statistics with properties
-- ============================================
CREATE OR REPLACE FUNCTION get_entity_stats()
RETURNS TABLE (
    entity_id TEXT,
    entity_name TEXT,
    entity_type TEXT,
    property_count BIGINT,
    total_tax_due NUMERIC,
    total_previous_year NUMERIC,
    extracted_count BIGINT,
    pending_count BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.entity_id,
        e.entity_name,
        e.entity_type,
        COUNT(p.id) as property_count,
        COALESCE(SUM(p.amount_due), 0) as total_tax_due,
        COALESCE(SUM(p.previous_year_taxes), 0) as total_previous_year,
        COUNT(CASE WHEN p.amount_due > 0 THEN 1 END) as extracted_count,
        COUNT(CASE WHEN p.amount_due IS NULL OR p.amount_due = 0 THEN 1 END) as pending_count
    FROM entities e
    LEFT JOIN properties p ON e.entity_id = p.entity_id
    GROUP BY e.entity_id, e.entity_name, e.entity_type
    ORDER BY property_count DESC;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION get_entity_stats() TO anon, authenticated;

-- ============================================
-- 5. Function for properties with entity info (joined)
-- ============================================
CREATE OR REPLACE FUNCTION get_properties_with_entities(
    p_limit INTEGER DEFAULT 100,
    p_offset INTEGER DEFAULT 0,
    p_jurisdiction TEXT DEFAULT NULL,
    p_state TEXT DEFAULT NULL,
    p_entity_id TEXT DEFAULT NULL,
    p_needs_extraction BOOLEAN DEFAULT NULL
)
RETURNS TABLE (
    property_id TEXT,
    property_name TEXT,
    property_address TEXT,
    jurisdiction TEXT,
    state TEXT,
    amount_due NUMERIC,
    previous_year_taxes NUMERIC,
    tax_due_date DATE,
    paid_by TEXT,
    tax_bill_link TEXT,
    entity_id TEXT,
    entity_name TEXT,
    entity_type TEXT,
    updated_at TIMESTAMP
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.id as property_id,
        p.property_name,
        p.property_address,
        p.jurisdiction,
        p.state,
        p.amount_due,
        p.previous_year_taxes,
        p.tax_due_date,
        p.paid_by,
        p.tax_bill_link,
        e.entity_id,
        e.entity_name,
        e.entity_type,
        p.updated_at
    FROM properties p
    LEFT JOIN entities e ON p.entity_id = e.entity_id
    WHERE 
        (p_jurisdiction IS NULL OR p.jurisdiction = p_jurisdiction)
        AND (p_state IS NULL OR p.state = p_state)
        AND (p_entity_id IS NULL OR p.entity_id = p_entity_id)
        AND (p_needs_extraction IS NULL OR 
             (p_needs_extraction = TRUE AND (p.amount_due IS NULL OR p.amount_due = 0)) OR
             (p_needs_extraction = FALSE AND p.amount_due > 0))
    ORDER BY p.updated_at DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION get_properties_with_entities TO anon, authenticated;

-- ============================================
-- 6. Materialized view for dashboard statistics
-- ============================================
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_stats AS
SELECT 
    COUNT(DISTINCT p.id) as total_properties,
    COUNT(DISTINCT e.entity_id) as total_entities,
    COUNT(DISTINCT p.jurisdiction) as total_jurisdictions,
    COUNT(DISTINCT p.state) as total_states,
    COALESCE(SUM(p.amount_due), 0) as total_outstanding,
    COALESCE(SUM(p.previous_year_taxes), 0) as total_previous,
    COUNT(CASE WHEN p.amount_due > 0 THEN 1 END) as extracted_count,
    COUNT(CASE WHEN p.amount_due IS NULL OR p.amount_due = 0 THEN 1 END) as pending_count,
    COUNT(CASE WHEN p.tax_due_date < CURRENT_DATE THEN 1 END) as overdue_count,
    COUNT(CASE WHEN p.tax_due_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days' THEN 1 END) as due_this_week,
    COUNT(CASE WHEN p.tax_due_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days' THEN 1 END) as due_this_month,
    MAX(p.updated_at) as last_update
FROM properties p
LEFT JOIN entities e ON p.entity_id = e.entity_id;

-- Create index for fast refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_dashboard_stats ON dashboard_stats (last_update);

-- Grant select permission
GRANT SELECT ON dashboard_stats TO anon, authenticated;

-- ============================================
-- 7. Function to refresh materialized view
-- ============================================
CREATE OR REPLACE FUNCTION refresh_dashboard_stats()
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_stats;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION refresh_dashboard_stats() TO anon, authenticated;

-- ============================================
-- 8. Trigger to auto-refresh stats on property updates
-- ============================================
CREATE OR REPLACE FUNCTION trigger_refresh_stats()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Debounce: Only refresh if last refresh was > 1 minute ago
    IF (SELECT last_update FROM dashboard_stats) < NOW() - INTERVAL '1 minute' THEN
        PERFORM refresh_dashboard_stats();
    END IF;
    RETURN NEW;
END;
$$;

-- Create trigger on properties table
DROP TRIGGER IF EXISTS refresh_stats_on_property_change ON properties;
CREATE TRIGGER refresh_stats_on_property_change
    AFTER INSERT OR UPDATE OR DELETE ON properties
    FOR EACH STATEMENT
    EXECUTE FUNCTION trigger_refresh_stats();

-- ============================================
-- 9. Indexes for performance optimization
-- ============================================

-- Index for filtering by jurisdiction
CREATE INDEX IF NOT EXISTS idx_properties_jurisdiction 
ON properties(jurisdiction) 
WHERE jurisdiction IS NOT NULL;

-- Index for filtering by state
CREATE INDEX IF NOT EXISTS idx_properties_state 
ON properties(state) 
WHERE state IS NOT NULL;

-- Index for filtering by entity_id
CREATE INDEX IF NOT EXISTS idx_properties_entity_id 
ON properties(entity_id) 
WHERE entity_id IS NOT NULL;

-- Composite index for common filters
CREATE INDEX IF NOT EXISTS idx_properties_filters 
ON properties(jurisdiction, state, entity_id, amount_due);

-- Index for extraction status queries
CREATE INDEX IF NOT EXISTS idx_properties_extraction_status 
ON properties(amount_due) 
WHERE amount_due IS NULL OR amount_due = 0;

-- Index for due date queries
CREATE INDEX IF NOT EXISTS idx_properties_due_date 
ON properties(tax_due_date) 
WHERE tax_due_date IS NOT NULL;

-- Index for updated_at for sorting
CREATE INDEX IF NOT EXISTS idx_properties_updated 
ON properties(updated_at DESC);

-- ============================================
-- 10. Function for batch property updates
-- ============================================
CREATE OR REPLACE FUNCTION batch_update_properties(
    updates JSONB
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    update_record JSONB;
BEGIN
    -- Loop through each update
    FOR update_record IN SELECT * FROM jsonb_array_elements(updates)
    LOOP
        UPDATE properties
        SET 
            amount_due = COALESCE((update_record->>'amount_due')::NUMERIC, amount_due),
            property_address = COALESCE(update_record->>'property_address', property_address),
            account_number = COALESCE(update_record->>'account_number', account_number),
            updated_at = NOW()
        WHERE id = update_record->>'id';
    END LOOP;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION batch_update_properties TO anon, authenticated;

-- ============================================
-- Initial refresh of materialized view
-- ============================================
REFRESH MATERIALIZED VIEW dashboard_stats;