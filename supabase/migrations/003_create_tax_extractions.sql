-- Create tax_extractions table to track extraction history
CREATE TABLE IF NOT EXISTS tax_extractions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL,
    entity_id UUID,
    extraction_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    tax_year INTEGER,
    amount_due DECIMAL(12, 2),
    amount_paid DECIMAL(12, 2),
    due_date DATE,
    payment_status VARCHAR(50), -- paid, pending, overdue, partial
    extraction_status VARCHAR(50), -- success, failed, partial, pending
    extraction_method VARCHAR(100), -- http, selenium, manual
    error_message TEXT,
    raw_data JSONB, -- Store raw extracted data
    metadata JSONB, -- Additional metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_extraction_property FOREIGN KEY (property_id) 
        REFERENCES properties(property_id) ON DELETE CASCADE,
    CONSTRAINT fk_extraction_entity FOREIGN KEY (entity_id) 
        REFERENCES entities(entity_id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX idx_tax_extractions_property_id ON tax_extractions(property_id);
CREATE INDEX idx_tax_extractions_entity_id ON tax_extractions(entity_id);
CREATE INDEX idx_tax_extractions_tax_year ON tax_extractions(tax_year);
CREATE INDEX idx_tax_extractions_extraction_date ON tax_extractions(extraction_date);
CREATE INDEX idx_tax_extractions_payment_status ON tax_extractions(payment_status);
CREATE INDEX idx_tax_extractions_extraction_status ON tax_extractions(extraction_status);

-- Add comments
COMMENT ON TABLE tax_extractions IS 'Historical record of all tax data extractions';
COMMENT ON COLUMN tax_extractions.property_id IS 'Reference to the property';
COMMENT ON COLUMN tax_extractions.entity_id IS 'Reference to the owning entity';
COMMENT ON COLUMN tax_extractions.tax_year IS 'Tax year for this extraction';
COMMENT ON COLUMN tax_extractions.payment_status IS 'Current payment status';
COMMENT ON COLUMN tax_extractions.extraction_status IS 'Status of the extraction attempt';
COMMENT ON COLUMN tax_extractions.extraction_method IS 'Method used for extraction';
COMMENT ON COLUMN tax_extractions.raw_data IS 'Raw extracted data in JSON format';
COMMENT ON COLUMN tax_extractions.metadata IS 'Additional metadata about the extraction';

-- Create trigger
CREATE TRIGGER update_tax_extractions_updated_at
    BEFORE UPDATE ON tax_extractions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();