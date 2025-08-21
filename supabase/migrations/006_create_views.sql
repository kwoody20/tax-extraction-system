-- Create view for property details with entity information
CREATE OR REPLACE VIEW property_details AS
SELECT 
    p.*,
    e.entity_name AS parent_entity_full_name,
    e.entity_type,
    e.close_date AS entity_close_date,
    j.jurisdiction_name AS jurisdiction_full_name,
    j.jurisdiction_type,
    j.tax_website_url,
    j.extraction_config
FROM properties p
LEFT JOIN entities e ON p.parent_entity_id = e.entity_id
LEFT JOIN jurisdictions j ON p.jurisdiction = j.jurisdiction_name;

-- Create view for entity portfolio summary
CREATE OR REPLACE VIEW entity_portfolio_summary AS
SELECT 
    e.entity_id,
    e.entity_name,
    e.entity_type,
    COUNT(DISTINCT p.property_id) AS property_count,
    COUNT(DISTINCT p.state) AS states_count,
    COUNT(DISTINCT p.jurisdiction) AS jurisdictions_count,
    SUM(p.amount_due) AS total_amount_due,
    SUM(p.previous_year_taxes) AS total_previous_year_taxes,
    MIN(p.close_date) AS earliest_acquisition,
    MAX(p.close_date) AS latest_acquisition
FROM entities e
LEFT JOIN properties p ON e.entity_id = p.parent_entity_id
GROUP BY e.entity_id, e.entity_name, e.entity_type;

-- Create view for recent extractions
CREATE OR REPLACE VIEW recent_extractions AS
SELECT 
    te.*,
    p.property_name,
    p.property_address,
    p.jurisdiction,
    p.state,
    e.entity_name
FROM tax_extractions te
JOIN properties p ON te.property_id = p.property_id
LEFT JOIN entities e ON te.entity_id = e.entity_id
WHERE te.extraction_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY te.extraction_date DESC;

-- Create view for extraction success metrics
CREATE OR REPLACE VIEW extraction_metrics AS
SELECT 
    DATE_TRUNC('day', extraction_date) AS extraction_day,
    COUNT(*) AS total_extractions,
    COUNT(CASE WHEN extraction_status = 'success' THEN 1 END) AS successful_extractions,
    COUNT(CASE WHEN extraction_status = 'failed' THEN 1 END) AS failed_extractions,
    COUNT(CASE WHEN extraction_status = 'partial' THEN 1 END) AS partial_extractions,
    ROUND(100.0 * COUNT(CASE WHEN extraction_status = 'success' THEN 1 END) / NULLIF(COUNT(*), 0), 2) AS success_rate,
    COUNT(DISTINCT property_id) AS unique_properties,
    COUNT(DISTINCT entity_id) AS unique_entities
FROM tax_extractions
GROUP BY DATE_TRUNC('day', extraction_date)
ORDER BY extraction_day DESC;

-- Create view for tax payment status overview
CREATE OR REPLACE VIEW tax_payment_overview AS
SELECT 
    p.state,
    p.jurisdiction,
    COUNT(DISTINCT p.property_id) AS total_properties,
    SUM(p.amount_due) AS total_amount_due,
    SUM(p.previous_year_taxes) AS total_previous_year_taxes,
    COUNT(CASE WHEN p.amount_due > 0 THEN 1 END) AS properties_with_balance,
    COUNT(CASE WHEN p.amount_due = 0 THEN 1 END) AS properties_paid,
    ROUND(AVG(p.amount_due), 2) AS avg_amount_due,
    ROUND(AVG(p.previous_year_taxes), 2) AS avg_previous_year_taxes
FROM properties p
GROUP BY p.state, p.jurisdiction
ORDER BY total_amount_due DESC;

-- Create materialized view for entity hierarchy (refreshable)
CREATE MATERIALIZED VIEW IF NOT EXISTS entity_hierarchy AS
WITH RECURSIVE entity_tree AS (
    -- Base case: top-level entities (no parent)
    SELECT 
        e.entity_id,
        e.entity_name,
        e.entity_type,
        NULL::UUID AS parent_id,
        0 AS level,
        ARRAY[e.entity_id] AS path,
        e.entity_name::TEXT AS full_path
    FROM entities e
    WHERE NOT EXISTS (
        SELECT 1 FROM entity_relationships er 
        WHERE er.child_entity_id = e.entity_id
    )
    
    UNION ALL
    
    -- Recursive case: child entities
    SELECT 
        e.entity_id,
        e.entity_name,
        e.entity_type,
        er.parent_entity_id AS parent_id,
        et.level + 1 AS level,
        et.path || e.entity_id AS path,
        (et.full_path || ' > ' || e.entity_name)::TEXT AS full_path
    FROM entities e
    JOIN entity_relationships er ON e.entity_id = er.child_entity_id
    JOIN entity_tree et ON er.parent_entity_id = et.entity_id
)
SELECT * FROM entity_tree;

-- Create index on materialized view
CREATE INDEX idx_entity_hierarchy_entity_id ON entity_hierarchy(entity_id);
CREATE INDEX idx_entity_hierarchy_parent_id ON entity_hierarchy(parent_id);
CREATE INDEX idx_entity_hierarchy_level ON entity_hierarchy(level);

-- Add comments for views
COMMENT ON VIEW property_details IS 'Comprehensive view of properties with entity and jurisdiction information';
COMMENT ON VIEW entity_portfolio_summary IS 'Summary statistics for each entity portfolio';
COMMENT ON VIEW recent_extractions IS 'Tax extractions from the last 30 days';
COMMENT ON VIEW extraction_metrics IS 'Daily extraction success metrics';
COMMENT ON VIEW tax_payment_overview IS 'Overview of tax payment status by state and jurisdiction';
COMMENT ON MATERIALIZED VIEW entity_hierarchy IS 'Hierarchical structure of entities (refreshable materialized view)';