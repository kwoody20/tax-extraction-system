-- Migration: Add document storage for tax documents, invoices, and bills
-- Version: 003
-- Date: 2024

-- Create document types enum
CREATE TYPE document_type AS ENUM (
    'tax_bill',
    'tax_receipt',
    'payment_confirmation',
    'assessment_notice',
    'invoice',
    'statement',
    'correspondence',
    'legal_document',
    'other'
);

-- Create document status enum
CREATE TYPE document_status AS ENUM (
    'pending',
    'processed',
    'archived',
    'failed'
);

-- Create tax_documents table
CREATE TABLE IF NOT EXISTS tax_documents (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
    entity_id UUID REFERENCES entities(id) ON DELETE SET NULL,
    jurisdiction VARCHAR(255) NOT NULL,
    
    -- Document metadata
    document_type document_type NOT NULL DEFAULT 'tax_bill',
    document_name VARCHAR(500) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),
    
    -- Storage information
    storage_path VARCHAR(1000),  -- Path in Supabase Storage
    storage_bucket VARCHAR(100) DEFAULT 'tax-documents',
    public_url TEXT,
    
    -- Document details
    tax_year INTEGER,
    tax_period VARCHAR(50),  -- e.g., "2024-Q1", "2024-Annual"
    amount_due DECIMAL(12, 2),
    due_date DATE,
    paid_date DATE,
    
    -- Extraction metadata
    extracted_from_url TEXT,
    extraction_date TIMESTAMP WITH TIME ZONE,
    extraction_method VARCHAR(50),  -- 'manual', 'automated', 'selenium', 'api'
    
    -- OCR and processing
    ocr_processed BOOLEAN DEFAULT FALSE,
    ocr_text TEXT,
    ocr_confidence FLOAT,
    extracted_data JSONB,  -- Structured data extracted from document
    
    -- Search and categorization
    tags TEXT[],
    notes TEXT,
    status document_status DEFAULT 'pending',
    
    -- Audit fields
    uploaded_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes for search
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(document_name, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(notes, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(ocr_text, '')), 'C')
    ) STORED
);

-- Create indexes for performance
CREATE INDEX idx_tax_documents_property_id ON tax_documents(property_id);
CREATE INDEX idx_tax_documents_entity_id ON tax_documents(entity_id);
CREATE INDEX idx_tax_documents_jurisdiction ON tax_documents(jurisdiction);
CREATE INDEX idx_tax_documents_tax_year ON tax_documents(tax_year);
CREATE INDEX idx_tax_documents_due_date ON tax_documents(due_date);
CREATE INDEX idx_tax_documents_status ON tax_documents(status);
CREATE INDEX idx_tax_documents_document_type ON tax_documents(document_type);
CREATE INDEX idx_tax_documents_search ON tax_documents USING GIN(search_vector);
CREATE INDEX idx_tax_documents_tags ON tax_documents USING GIN(tags);

-- Create document_versions table for version control
CREATE TABLE IF NOT EXISTS document_versions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    document_id UUID REFERENCES tax_documents(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    storage_path VARCHAR(1000),
    file_size INTEGER,
    uploaded_by VARCHAR(255),
    upload_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(document_id, version_number)
);

-- Create document_extraction_queue table
CREATE TABLE IF NOT EXISTS document_extraction_queue (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    jurisdiction VARCHAR(255),
    extraction_type VARCHAR(50) DEFAULT 'tax_bill',
    priority INTEGER DEFAULT 5,  -- 1-10, 1 being highest priority
    status VARCHAR(50) DEFAULT 'queued',  -- queued, processing, completed, failed
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    -- Results
    document_id UUID REFERENCES tax_documents(id) ON DELETE SET NULL,
    error_message TEXT,
    
    -- Timestamps
    queued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    metadata JSONB
);

-- Create document_payments table to track payments
CREATE TABLE IF NOT EXISTS document_payments (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    document_id UUID REFERENCES tax_documents(id) ON DELETE CASCADE,
    property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
    
    payment_amount DECIMAL(12, 2) NOT NULL,
    payment_date DATE NOT NULL,
    payment_method VARCHAR(50),  -- 'check', 'ach', 'credit_card', 'wire', 'cash'
    confirmation_number VARCHAR(100),
    
    paid_by VARCHAR(50),  -- 'landlord', 'tenant', 'property_manager'
    notes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create views for document analytics
CREATE OR REPLACE VIEW document_summary AS
SELECT 
    p.property_name,
    p.jurisdiction,
    COUNT(DISTINCT td.id) as total_documents,
    COUNT(DISTINCT CASE WHEN td.document_type = 'tax_bill' THEN td.id END) as tax_bills,
    COUNT(DISTINCT CASE WHEN td.document_type = 'tax_receipt' THEN td.id END) as receipts,
    COUNT(DISTINCT CASE WHEN td.status = 'pending' THEN td.id END) as pending_documents,
    MAX(td.created_at) as last_document_date,
    SUM(td.amount_due) as total_amount_due
FROM properties p
LEFT JOIN tax_documents td ON p.id = td.property_id
GROUP BY p.id, p.property_name, p.jurisdiction;

-- Create view for upcoming payments
CREATE OR REPLACE VIEW upcoming_payments AS
SELECT 
    td.id as document_id,
    td.property_id,
    p.property_name,
    p.jurisdiction,
    td.document_name,
    td.amount_due,
    td.due_date,
    td.paid_date,
    CASE 
        WHEN td.paid_date IS NOT NULL THEN 'paid'
        WHEN td.due_date < CURRENT_DATE THEN 'overdue'
        WHEN td.due_date <= CURRENT_DATE + INTERVAL '7 days' THEN 'due_soon'
        ELSE 'upcoming'
    END as payment_status
FROM tax_documents td
JOIN properties p ON td.property_id = p.id
WHERE td.document_type IN ('tax_bill', 'invoice')
    AND td.amount_due > 0
ORDER BY td.due_date;

-- RLS Policies for documents
ALTER TABLE tax_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_extraction_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_payments ENABLE ROW LEVEL SECURITY;

-- Create RLS policies (adjust based on your auth setup)
CREATE POLICY "Allow authenticated users to view documents"
    ON tax_documents FOR SELECT
    USING (auth.role() = 'authenticated');

CREATE POLICY "Allow authenticated users to insert documents"
    ON tax_documents FOR INSERT
    WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Allow authenticated users to update documents"
    ON tax_documents FOR UPDATE
    USING (auth.role() = 'authenticated');

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_document_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers
CREATE TRIGGER update_tax_documents_updated_at
    BEFORE UPDATE ON tax_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_document_updated_at();

CREATE TRIGGER update_document_payments_updated_at
    BEFORE UPDATE ON document_payments
    FOR EACH ROW
    EXECUTE FUNCTION update_document_updated_at();

-- Create function to auto-increment version number
CREATE OR REPLACE FUNCTION increment_document_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.version_number := COALESCE(
        (SELECT MAX(version_number) + 1 
         FROM document_versions 
         WHERE document_id = NEW.document_id), 
        1
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auto_increment_version
    BEFORE INSERT ON document_versions
    FOR EACH ROW
    EXECUTE FUNCTION increment_document_version();

-- Sample data for testing (optional)
/*
INSERT INTO tax_documents (
    property_id,
    jurisdiction,
    document_type,
    document_name,
    file_name,
    tax_year,
    amount_due,
    due_date
) VALUES (
    (SELECT id FROM properties LIMIT 1),
    'Harris County',
    'tax_bill',
    '2024 Property Tax Bill - Harris County',
    '2024_harris_county_tax_bill.pdf',
    2024,
    5432.10,
    '2024-01-31'
);
*/

-- Grant permissions
GRANT ALL ON tax_documents TO authenticated;
GRANT ALL ON document_versions TO authenticated;
GRANT ALL ON document_extraction_queue TO authenticated;
GRANT ALL ON document_payments TO authenticated;
GRANT SELECT ON document_summary TO authenticated;
GRANT SELECT ON upcoming_payments TO authenticated;