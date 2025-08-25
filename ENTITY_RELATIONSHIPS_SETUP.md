# Entity Relationships Setup Guide

## Current Status
- The entities table has 44 entities (23 parent, 5 sub-entities, 16 single-property)
- Sub-entities need to be linked to their parent entities
- The entity_relationships table exists but needs proper permissions

## Required Database Changes

### Option 1: Add parent_entity_id column to entities table

```sql
-- Add parent_entity_id column to entities table
ALTER TABLE entities 
ADD COLUMN parent_entity_id UUID REFERENCES entities(entity_id);

-- Update the sub-entities with their parent relationships
UPDATE entities 
SET parent_entity_id = 'a88691c4-f324-4ec0-b8f6-8c97043f21a8'
WHERE entity_id = 'faf56ed2-969c-45d1-be0e-f181d1e8df08';
-- Links: BCS Mont Belvieu LLC - Barbers Hill ISD -> BCS Mont Belvieu LLC (TX)

UPDATE entities 
SET parent_entity_id = 'b9780684-64da-4b87-b83b-af82142375c1'
WHERE entity_id = '6a647fd8-b963-4a57-ad82-55cf8e145f5c';
-- Links: BCS Baytown Grove LLC - Goose Creek ISD -> BCS Baytown Grove LLC (TX)

UPDATE entities 
SET parent_entity_id = '3694b20c-63a3-40c5-b0d9-faadf01e2532'
WHERE entity_id = '9b920002-25c8-4e91-b897-ba57eca10c40';
-- Links: BCS Montgomery LLC - 32 Acres -> BCS Montgomery LLC (TX) - 33 Acres

UPDATE entities 
SET parent_entity_id = '3a5c8559-5d4c-4a4a-8f36-43e7dea884a2'
WHERE entity_id = 'ddb6f249-708b-4e35-acaa-03bd8c73ee22';
-- Links: 3202 Riley Fuzzell Rd -> BCS Magnolia Place LLC (TX)

UPDATE entities 
SET parent_entity_id = '3694b20c-63a3-40c5-b0d9-faadf01e2532'
WHERE entity_id = '0830cbcf-ae79-42ea-ac70-33716d2d2b7a';
-- Links: BCS Montgomery LLC - 6.59 Acres -> BCS Montgomery LLC (TX) - 33 Acres

-- Add index for performance
CREATE INDEX idx_entities_parent_entity_id ON entities(parent_entity_id);
```

### Option 2: Use entity_relationships table

```sql
-- Grant permissions to the entity_relationships table
GRANT ALL ON entity_relationships TO anon;
GRANT ALL ON entity_relationships TO authenticated;

-- Insert the relationships
INSERT INTO entity_relationships (parent_entity_id, child_entity_id, relationship_type)
VALUES 
  ('a88691c4-f324-4ec0-b8f6-8c97043f21a8', 'faf56ed2-969c-45d1-be0e-f181d1e8df08', 'parent-child'),
  ('b9780684-64da-4b87-b83b-af82142375c1', '6a647fd8-b963-4a57-ad82-55cf8e145f5c', 'parent-child'),
  ('3694b20c-63a3-40c5-b0d9-faadf01e2532', '9b920002-25c8-4e91-b897-ba57eca10c40', 'parent-child'),
  ('3a5c8559-5d4c-4a4a-8f36-43e7dea884a2', 'ddb6f249-708b-4e35-acaa-03bd8c73ee22', 'parent-child'),
  ('3694b20c-63a3-40c5-b0d9-faadf01e2532', '0830cbcf-ae79-42ea-ac70-33716d2d2b7a', 'parent-child');
```

## Relationship Mappings

| Sub-Entity | Sub-Entity ID | Parent Entity | Parent Entity ID |
|------------|---------------|---------------|------------------|
| BCS Mont Belvieu LLC - Barbers Hill ISD: (Total 5.33 Acres) | faf56ed2-969c-45d1-be0e-f181d1e8df08 | BCS Mont Belvieu LLC (TX) - Total 5.33 Acres (Remaining 4.3260 Acres) | a88691c4-f324-4ec0-b8f6-8c97043f21a8 |
| BCS Baytown Grove LLC - Goose Creek ISD: (Total 35.430 Acres) - Pending 11 Acre Bill? | 6a647fd8-b963-4a57-ad82-55cf8e145f5c | BCS Baytown Grove LLC (TX) - Total 47 Acres (entity, untaxed) | b9780684-64da-4b87-b83b-af82142375c1 |
| BCS Montgomery LLC - 32 Acres | 9b920002-25c8-4e91-b897-ba57eca10c40 | BCS Montgomery LLC (TX) - 33 Acres | 3694b20c-63a3-40c5-b0d9-faadf01e2532 |
| 3202 Riley Fuzzell Rd - (18.1 acres): | ddb6f249-708b-4e35-acaa-03bd8c73ee22 | BCS Magnolia Place LLC (TX) - Total 51.13 Acres | 3a5c8559-5d4c-4a4a-8f36-43e7dea884a2 |
| BCS Montgomery LLC - 6.59 Acres: | 0830cbcf-ae79-42ea-ac70-33716d2d2b7a | BCS Montgomery LLC (TX) - 33 Acres | 3694b20c-63a3-40c5-b0d9-faadf01e2532 |

## How to Apply These Changes

1. **Via Supabase Dashboard:**
   - Go to SQL Editor in your Supabase dashboard
   - Copy and paste the SQL commands from Option 1 or Option 2 above
   - Execute the commands

2. **Via Direct Database Connection:**
   - Use the database connection string from Supabase
   - Connect using psql or any PostgreSQL client
   - Execute the SQL commands

## Verification

After applying the changes, you can verify with:

```sql
-- For Option 1 (parent_entity_id column):
SELECT 
  e.entity_name as sub_entity,
  p.entity_name as parent_entity
FROM entities e
JOIN entities p ON e.parent_entity_id = p.entity_id
WHERE e.entity_type = 'sub-entity';

-- For Option 2 (entity_relationships table):
SELECT 
  c.entity_name as sub_entity,
  p.entity_name as parent_entity
FROM entity_relationships r
JOIN entities c ON r.child_entity_id = c.entity_id
JOIN entities p ON r.parent_entity_id = p.entity_id;
```

## Dashboard Updates Required

Once the relationships are established, the dashboard will automatically:
- Show the entity hierarchy network visualization
- Display parent entity names for sub-entities
- Properly categorize entities based on their types