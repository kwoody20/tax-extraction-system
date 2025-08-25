-- Add parent_entity_id column to entities table
ALTER TABLE entities 
ADD COLUMN IF NOT EXISTS parent_entity_id UUID REFERENCES entities(entity_id);

-- Add an index for faster lookups
CREATE INDEX IF NOT EXISTS idx_entities_parent_entity_id ON entities(parent_entity_id);

-- Add comment for documentation
COMMENT ON COLUMN entities.parent_entity_id IS 'Reference to parent entity for sub-entities';