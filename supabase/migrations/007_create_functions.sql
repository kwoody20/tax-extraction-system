-- Function to get entity with all its properties
CREATE OR REPLACE FUNCTION get_entity_with_properties(p_entity_id UUID)
RETURNS TABLE (
    entity_id UUID,
    entity_name VARCHAR,
    entity_type VARCHAR,
    property_count BIGINT,
    total_amount_due DECIMAL,
    total_previous_year_taxes DECIMAL,
    properties JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.entity_id,
        e.entity_name,
        e.entity_type,
        COUNT(p.property_id) AS property_count,
        SUM(p.amount_due) AS total_amount_due,
        SUM(p.previous_year_taxes) AS total_previous_year_taxes,
        JSONB_AGG(
            JSONB_BUILD_OBJECT(
                'property_id', p.property_id,
                'property_name', p.property_name,
                'jurisdiction', p.jurisdiction,
                'state', p.state,
                'amount_due', p.amount_due,
                'tax_bill_link', p.tax_bill_link
            ) ORDER BY p.property_name
        ) AS properties
    FROM entities e
    LEFT JOIN properties p ON e.entity_id = p.parent_entity_id
    WHERE e.entity_id = p_entity_id
    GROUP BY e.entity_id, e.entity_name, e.entity_type;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate tax statistics for a given period
CREATE OR REPLACE FUNCTION calculate_tax_statistics(
    p_start_date DATE DEFAULT NULL,
    p_end_date DATE DEFAULT NULL
)
RETURNS TABLE (
    total_properties BIGINT,
    total_entities BIGINT,
    total_amount_due DECIMAL,
    total_previous_year_taxes DECIMAL,
    avg_amount_due DECIMAL,
    max_amount_due DECIMAL,
    min_amount_due DECIMAL,
    properties_with_balance BIGINT,
    properties_paid BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(DISTINCT p.property_id) AS total_properties,
        COUNT(DISTINCT p.parent_entity_id) AS total_entities,
        SUM(p.amount_due) AS total_amount_due,
        SUM(p.previous_year_taxes) AS total_previous_year_taxes,
        AVG(p.amount_due) AS avg_amount_due,
        MAX(p.amount_due) AS max_amount_due,
        MIN(p.amount_due) AS min_amount_due,
        COUNT(CASE WHEN p.amount_due > 0 THEN 1 END) AS properties_with_balance,
        COUNT(CASE WHEN p.amount_due = 0 THEN 1 END) AS properties_paid
    FROM properties p
    WHERE (p_start_date IS NULL OR p.close_date >= p_start_date)
      AND (p_end_date IS NULL OR p.close_date <= p_end_date);
END;
$$ LANGUAGE plpgsql;

-- Function to find properties needing extraction
CREATE OR REPLACE FUNCTION find_properties_needing_extraction(
    p_days_since_last INTEGER DEFAULT 30
)
RETURNS TABLE (
    property_id UUID,
    property_name VARCHAR,
    jurisdiction VARCHAR,
    state VARCHAR,
    tax_bill_link TEXT,
    last_extraction_date TIMESTAMP WITH TIME ZONE,
    days_since_extraction INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.property_id,
        p.property_name,
        p.jurisdiction,
        p.state,
        p.tax_bill_link,
        MAX(te.extraction_date) AS last_extraction_date,
        EXTRACT(DAY FROM CURRENT_TIMESTAMP - MAX(te.extraction_date))::INTEGER AS days_since_extraction
    FROM properties p
    LEFT JOIN tax_extractions te ON p.property_id = te.property_id
    WHERE p.tax_bill_link IS NOT NULL
    GROUP BY p.property_id, p.property_name, p.jurisdiction, p.state, p.tax_bill_link
    HAVING MAX(te.extraction_date) IS NULL 
        OR EXTRACT(DAY FROM CURRENT_TIMESTAMP - MAX(te.extraction_date)) >= p_days_since_last
    ORDER BY days_since_extraction DESC NULLS FIRST;
END;
$$ LANGUAGE plpgsql;

-- Function to insert or update property
CREATE OR REPLACE FUNCTION upsert_property(
    p_property_id UUID,
    p_property_name VARCHAR,
    p_sub_entity VARCHAR DEFAULT NULL,
    p_parent_entity_name VARCHAR DEFAULT NULL,
    p_jurisdiction VARCHAR DEFAULT NULL,
    p_state VARCHAR DEFAULT NULL,
    p_property_type VARCHAR DEFAULT NULL,
    p_close_date DATE DEFAULT NULL,
    p_amount_due DECIMAL DEFAULT NULL,
    p_previous_year_taxes DECIMAL DEFAULT NULL,
    p_extraction_steps TEXT DEFAULT NULL,
    p_account_number VARCHAR DEFAULT NULL,
    p_property_address TEXT DEFAULT NULL,
    p_tax_bill_link TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_parent_entity_id UUID;
    v_result_id UUID;
BEGIN
    -- Find parent entity ID if name is provided
    IF p_parent_entity_name IS NOT NULL THEN
        SELECT entity_id INTO v_parent_entity_id
        FROM entities
        WHERE entity_name = p_parent_entity_name
        LIMIT 1;
    END IF;
    
    -- Insert or update property
    INSERT INTO properties (
        property_id,
        property_name,
        sub_entity,
        parent_entity_id,
        parent_entity_name,
        jurisdiction,
        state,
        property_type,
        close_date,
        amount_due,
        previous_year_taxes,
        extraction_steps,
        account_number,
        property_address,
        tax_bill_link
    ) VALUES (
        p_property_id,
        p_property_name,
        p_sub_entity,
        v_parent_entity_id,
        p_parent_entity_name,
        p_jurisdiction,
        p_state,
        p_property_type,
        p_close_date,
        p_amount_due,
        p_previous_year_taxes,
        p_extraction_steps,
        p_account_number,
        p_property_address,
        p_tax_bill_link
    )
    ON CONFLICT (property_id) DO UPDATE SET
        property_name = EXCLUDED.property_name,
        sub_entity = EXCLUDED.sub_entity,
        parent_entity_id = EXCLUDED.parent_entity_id,
        parent_entity_name = EXCLUDED.parent_entity_name,
        jurisdiction = EXCLUDED.jurisdiction,
        state = EXCLUDED.state,
        property_type = EXCLUDED.property_type,
        close_date = EXCLUDED.close_date,
        amount_due = EXCLUDED.amount_due,
        previous_year_taxes = EXCLUDED.previous_year_taxes,
        extraction_steps = EXCLUDED.extraction_steps,
        account_number = EXCLUDED.account_number,
        property_address = EXCLUDED.property_address,
        tax_bill_link = EXCLUDED.tax_bill_link,
        updated_at = CURRENT_TIMESTAMP
    RETURNING id INTO v_result_id;
    
    RETURN v_result_id;
END;
$$ LANGUAGE plpgsql;

-- Function to record extraction result
CREATE OR REPLACE FUNCTION record_extraction_result(
    p_property_id UUID,
    p_entity_id UUID DEFAULT NULL,
    p_tax_year INTEGER DEFAULT EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER,
    p_amount_due DECIMAL DEFAULT NULL,
    p_amount_paid DECIMAL DEFAULT NULL,
    p_due_date DATE DEFAULT NULL,
    p_payment_status VARCHAR DEFAULT 'pending',
    p_extraction_status VARCHAR DEFAULT 'success',
    p_extraction_method VARCHAR DEFAULT 'http',
    p_error_message TEXT DEFAULT NULL,
    p_raw_data JSONB DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_extraction_id UUID;
BEGIN
    INSERT INTO tax_extractions (
        property_id,
        entity_id,
        tax_year,
        amount_due,
        amount_paid,
        due_date,
        payment_status,
        extraction_status,
        extraction_method,
        error_message,
        raw_data,
        metadata
    ) VALUES (
        p_property_id,
        p_entity_id,
        p_tax_year,
        p_amount_due,
        p_amount_paid,
        p_due_date,
        p_payment_status,
        p_extraction_status,
        p_extraction_method,
        p_error_message,
        p_raw_data,
        p_metadata
    ) RETURNING id INTO v_extraction_id;
    
    -- Update property with latest extraction data if successful
    IF p_extraction_status = 'success' AND p_amount_due IS NOT NULL THEN
        UPDATE properties 
        SET amount_due = p_amount_due,
            updated_at = CURRENT_TIMESTAMP
        WHERE property_id = p_property_id;
    END IF;
    
    RETURN v_extraction_id;
END;
$$ LANGUAGE plpgsql;

-- Add comments for functions
COMMENT ON FUNCTION get_entity_with_properties IS 'Get entity details with all associated properties';
COMMENT ON FUNCTION calculate_tax_statistics IS 'Calculate tax statistics for a given date range';
COMMENT ON FUNCTION find_properties_needing_extraction IS 'Find properties that need tax data extraction';
COMMENT ON FUNCTION upsert_property IS 'Insert or update a property record';
COMMENT ON FUNCTION record_extraction_result IS 'Record the result of a tax extraction attempt';