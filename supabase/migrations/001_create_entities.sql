-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create entities table
CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id UUID UNIQUE NOT NULL, -- Original ID from CSV
    entity_name VARCHAR(255) NOT NULL,
    jurisdiction VARCHAR(255),
    state VARCHAR(50),
    entity_type VARCHAR(100), -- parent entity, subsidiary, etc.
    close_date DATE,
    amount_due DECIMAL(12, 2),
    previous_year_taxes DECIMAL(12, 2),
    extraction_steps TEXT,
    account_number VARCHAR(100),
    property_address TEXT,
    tax_bill_link TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_entities_entity_id ON entities(entity_id);
CREATE INDEX idx_entities_entity_name ON entities(entity_name);
CREATE INDEX idx_entities_state ON entities(state);
CREATE INDEX idx_entities_jurisdiction ON entities(jurisdiction);
CREATE INDEX idx_entities_entity_type ON entities(entity_type);

-- Add comments
COMMENT ON TABLE entities IS 'Parent entities and organizations that own properties';
COMMENT ON COLUMN entities.entity_id IS 'Original UUID from source data';
COMMENT ON COLUMN entities.entity_name IS 'Name of the entity/organization';
COMMENT ON COLUMN entities.entity_type IS 'Type of entity (parent entity, subsidiary, etc.)';
COMMENT ON COLUMN entities.close_date IS 'Closing or acquisition date';
COMMENT ON COLUMN entities.amount_due IS 'Current amount due for taxes';
COMMENT ON COLUMN entities.previous_year_taxes IS 'Previous year tax amount';

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_entities_updated_at
    BEFORE UPDATE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();