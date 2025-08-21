-- Create properties table
CREATE TABLE IF NOT EXISTS properties (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID UNIQUE NOT NULL, -- Original ID from CSV
    property_name VARCHAR(500) NOT NULL,
    sub_entity VARCHAR(255),
    parent_entity_id UUID, -- Foreign key to entities table
    parent_entity_name VARCHAR(255), -- Denormalized for performance
    jurisdiction VARCHAR(255),
    state VARCHAR(50),
    property_type VARCHAR(100),
    close_date DATE,
    amount_due DECIMAL(12, 2),
    previous_year_taxes DECIMAL(12, 2),
    extraction_steps TEXT,
    account_number VARCHAR(100),
    property_address TEXT,
    tax_bill_link TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_parent_entity FOREIGN KEY (parent_entity_id) 
        REFERENCES entities(entity_id) ON DELETE SET NULL
);

-- Create indexes for performance
CREATE INDEX idx_properties_property_id ON properties(property_id);
CREATE INDEX idx_properties_property_name ON properties(property_name);
CREATE INDEX idx_properties_parent_entity_id ON properties(parent_entity_id);
CREATE INDEX idx_properties_parent_entity_name ON properties(parent_entity_name);
CREATE INDEX idx_properties_state ON properties(state);
CREATE INDEX idx_properties_jurisdiction ON properties(jurisdiction);
CREATE INDEX idx_properties_property_type ON properties(property_type);
CREATE INDEX idx_properties_account_number ON properties(account_number);

-- Add comments
COMMENT ON TABLE properties IS 'Individual properties with tax information';
COMMENT ON COLUMN properties.property_id IS 'Original UUID from source data';
COMMENT ON COLUMN properties.property_name IS 'Name or description of the property';
COMMENT ON COLUMN properties.sub_entity IS 'Sub-entity or additional grouping';
COMMENT ON COLUMN properties.parent_entity_id IS 'Foreign key reference to entities table';
COMMENT ON COLUMN properties.parent_entity_name IS 'Denormalized entity name for query performance';
COMMENT ON COLUMN properties.property_type IS 'Type of property (commercial, residential, land, etc.)';
COMMENT ON COLUMN properties.close_date IS 'Property closing or acquisition date';
COMMENT ON COLUMN properties.amount_due IS 'Current tax amount due';
COMMENT ON COLUMN properties.previous_year_taxes IS 'Previous year tax amount';
COMMENT ON COLUMN properties.extraction_steps IS 'Instructions for extracting tax data';
COMMENT ON COLUMN properties.tax_bill_link IS 'URL to online tax bill';

-- Create trigger to update updated_at timestamp
CREATE TRIGGER update_properties_updated_at
    BEFORE UPDATE ON properties
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();