-- Add tax_due_date and paid_by columns to properties table
-- Migration: 012_add_tax_due_date_and_paid_by.sql

-- Add tax_due_date column
ALTER TABLE properties 
ADD COLUMN IF NOT EXISTS tax_due_date DATE;

-- Add paid_by column
ALTER TABLE properties 
ADD COLUMN IF NOT EXISTS paid_by VARCHAR(50);

-- Add comments for new columns
COMMENT ON COLUMN properties.tax_due_date IS 'Date when property tax payment is due';
COMMENT ON COLUMN properties.paid_by IS 'Party responsible for paying the tax (Landlord, Tenant, Tenant to Reimburse, Ryan Tax)';

-- Create index on tax_due_date for efficient filtering
CREATE INDEX IF NOT EXISTS idx_properties_tax_due_date ON properties(tax_due_date);

-- Create index on paid_by for efficient filtering
CREATE INDEX IF NOT EXISTS idx_properties_paid_by ON properties(paid_by);

-- Add check constraint for valid paid_by values
ALTER TABLE properties
ADD CONSTRAINT check_paid_by_values 
CHECK (paid_by IS NULL OR paid_by IN ('Landlord', 'Tenant', 'Tenant to Reimburse', 'Ryan Tax'));