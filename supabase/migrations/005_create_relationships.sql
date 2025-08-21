-- Create entity_relationships table for tracking entity hierarchies
CREATE TABLE IF NOT EXISTS entity_relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_entity_id UUID NOT NULL,
    child_entity_id UUID NOT NULL,
    relationship_type VARCHAR(100), -- subsidiary, division, acquisition, etc.
    effective_date DATE,
    end_date DATE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_parent_entity_rel FOREIGN KEY (parent_entity_id) 
        REFERENCES entities(entity_id) ON DELETE CASCADE,
    CONSTRAINT fk_child_entity_rel FOREIGN KEY (child_entity_id) 
        REFERENCES entities(entity_id) ON DELETE CASCADE,
    CONSTRAINT unique_entity_relationship UNIQUE (parent_entity_id, child_entity_id, relationship_type)
);

-- Create indexes
CREATE INDEX idx_entity_relationships_parent ON entity_relationships(parent_entity_id);
CREATE INDEX idx_entity_relationships_child ON entity_relationships(child_entity_id);
CREATE INDEX idx_entity_relationships_type ON entity_relationships(relationship_type);

-- Add comments
COMMENT ON TABLE entity_relationships IS 'Hierarchical relationships between entities';
COMMENT ON COLUMN entity_relationships.parent_entity_id IS 'Parent entity in the relationship';
COMMENT ON COLUMN entity_relationships.child_entity_id IS 'Child entity in the relationship';
COMMENT ON COLUMN entity_relationships.relationship_type IS 'Type of relationship';
COMMENT ON COLUMN entity_relationships.effective_date IS 'When the relationship became effective';
COMMENT ON COLUMN entity_relationships.end_date IS 'When the relationship ended (if applicable)';

-- Create trigger
CREATE TRIGGER update_entity_relationships_updated_at
    BEFORE UPDATE ON entity_relationships
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();