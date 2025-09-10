-- Create jurisdictions table for managing tax jurisdictions
CREATE TABLE IF NOT EXISTS jurisdictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    jurisdiction_name VARCHAR(255) UNIQUE NOT NULL,
    state VARCHAR(50),
    jurisdiction_type VARCHAR(100), -- county, city, district, ISD
    tax_website_url TEXT,
    extraction_config JSONB, -- Store extraction configuration
    rate_limit_delay INTEGER DEFAULT 2, -- Seconds between requests
    max_retries INTEGER DEFAULT 3,
    is_active BOOLEAN DEFAULT true,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes (idempotent)
CREATE INDEX IF NOT EXISTS idx_jurisdictions_name ON jurisdictions(jurisdiction_name);
CREATE INDEX IF NOT EXISTS idx_jurisdictions_state ON jurisdictions(state);
CREATE INDEX IF NOT EXISTS idx_jurisdictions_type ON jurisdictions(jurisdiction_type);
CREATE INDEX IF NOT EXISTS idx_jurisdictions_active ON jurisdictions(is_active);

-- Add comments
COMMENT ON TABLE jurisdictions IS 'Tax jurisdictions and their extraction configurations';
COMMENT ON COLUMN jurisdictions.jurisdiction_name IS 'Name of the tax jurisdiction';
COMMENT ON COLUMN jurisdictions.jurisdiction_type IS 'Type of jurisdiction (county, city, district, etc.)';
COMMENT ON COLUMN jurisdictions.tax_website_url IS 'Base URL for the jurisdiction tax website';
COMMENT ON COLUMN jurisdictions.extraction_config IS 'JSON configuration for extraction methods';
COMMENT ON COLUMN jurisdictions.rate_limit_delay IS 'Delay in seconds between extraction requests';

-- Create trigger
CREATE TRIGGER update_jurisdictions_updated_at
    BEFORE UPDATE ON jurisdictions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
