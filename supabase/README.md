# Supabase Database Schema for Property Tax Extraction System

This directory contains the database schema and migration files for the property tax extraction system using Supabase.

## Database Structure

### Core Tables

1. **entities** - Parent organizations that own properties
   - Stores entity information like name, type, jurisdiction, state
   - Tracks tax amounts and closing dates
   - Links to multiple properties

2. **properties** - Individual properties with tax information
   - Contains property details, addresses, and tax amounts
   - Links to parent entities
   - Stores extraction instructions and tax bill URLs

3. **tax_extractions** - Historical record of all extraction attempts
   - Tracks extraction status, methods, and results
   - Stores raw extracted data in JSON format
   - Links to properties and entities

4. **jurisdictions** - Tax jurisdiction configurations
   - Stores extraction settings per jurisdiction
   - Contains rate limiting and retry configurations
   - Manages jurisdiction-specific extraction methods

5. **entity_relationships** - Hierarchical relationships between entities
   - Tracks parent-child relationships
   - Supports subsidiary and acquisition tracking

### Views

- **property_details** - Comprehensive property information with entity data
- **entity_portfolio_summary** - Summary statistics per entity
- **recent_extractions** - Last 30 days of extraction activity
- **extraction_metrics** - Daily extraction success metrics
- **tax_payment_overview** - Payment status by state/jurisdiction
- **entity_hierarchy** - Materialized view of entity relationships

### Functions

- `get_entity_with_properties()` - Get entity with all properties
- `calculate_tax_statistics()` - Calculate tax statistics for date ranges
- `find_properties_needing_extraction()` - Identify properties for extraction
- `upsert_property()` - Insert or update property records
- `record_extraction_result()` - Record extraction attempts

## Setup Instructions

### 1. Create Supabase Project

1. Go to [Supabase](https://supabase.com)
2. Create a new project
3. Note your project URL and anon/service keys

### 2. Run Migrations

Execute the migration files in order:

```bash
# Using Supabase CLI
supabase db push

# Or manually in SQL Editor:
# Run each file in order from 001 to 008
```

### 3. Configure Environment

Create a `.env` file:

```env
SUPABASE_URL=your-project-url
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
```

### 4. Import Data

Use the Python client to import your CSV data:

```python
from supabase_client import SupabasePropertyTaxClient

client = SupabasePropertyTaxClient()

# Import entities
entity_results = client.bulk_import_entities_from_csv("entities-proptax-8202025.csv")
print(f"Entities: {entity_results['success']} imported")

# Import properties
property_results = client.bulk_import_properties_from_csv("OFFICIAL-proptax-assets.csv")
print(f"Properties: {property_results['success']} imported")
```

## Usage Examples

### Python Client

```python
from supabase_client import SupabasePropertyTaxClient

# Initialize client
client = SupabasePropertyTaxClient()

# Get properties needing extraction
properties = client.find_properties_needing_extraction(days_since_last=30)

# Record extraction result
client.record_extraction({
    "p_property_id": "property-uuid",
    "p_amount_due": 5000.00,
    "p_extraction_status": "success",
    "p_extraction_method": "selenium"
})

# Get entity portfolio
summary = client.get_entity_portfolio_summary()
```

### Async Operations

```python
import asyncio
from supabase_client import AsyncSupabasePropertyTaxClient

async def process_extractions():
    async with AsyncSupabasePropertyTaxClient() as client:
        properties = await client.get_properties_needing_extraction()
        # Process properties...
        
asyncio.run(process_extractions())
```

### Direct SQL Queries

```sql
-- Find properties with high tax amounts
SELECT * FROM properties 
WHERE amount_due > 10000 
ORDER BY amount_due DESC;

-- Get extraction success rate by jurisdiction
SELECT 
    jurisdiction,
    COUNT(*) as total,
    AVG(CASE WHEN extraction_status = 'success' THEN 1 ELSE 0 END) * 100 as success_rate
FROM tax_extractions te
JOIN properties p ON te.property_id = p.property_id
GROUP BY jurisdiction;

-- Get entity tax totals
SELECT * FROM entity_portfolio_summary
ORDER BY total_amount_due DESC;
```

## Security

- Row Level Security (RLS) is enabled on all tables
- Policies restrict access to authenticated users
- Service role has full access for backend operations
- Anonymous users have read-only access to views

## Integration with Tax Extraction System

The database integrates with the extraction system:

1. **Before Extraction**: Query `find_properties_needing_extraction()`
2. **During Extraction**: Update status in real-time
3. **After Extraction**: Call `record_extraction_result()`
4. **Monitoring**: Use views for dashboards and reporting

## Maintenance

### Refresh Materialized View

```sql
REFRESH MATERIALIZED VIEW entity_hierarchy;
```

### Clean Old Extractions

```sql
DELETE FROM tax_extractions 
WHERE extraction_date < CURRENT_DATE - INTERVAL '1 year';
```

### Update Statistics

```sql
ANALYZE entities;
ANALYZE properties;
ANALYZE tax_extractions;
```

## Performance Considerations

- Indexes on foreign keys and commonly queried columns
- Materialized view for complex hierarchy queries
- JSONB columns for flexible metadata storage
- Denormalized parent_entity_name in properties for faster queries

## Backup and Recovery

Supabase automatically handles:
- Daily backups (retained for 7-30 days based on plan)
- Point-in-time recovery
- Logical replication for real-time sync

Manual backup:
```bash
pg_dump $DATABASE_URL > backup.sql
```

## Support

For database-specific issues:
- Check Supabase logs in dashboard
- Review function execution in SQL editor
- Monitor RLS policies for access issues
- Use EXPLAIN ANALYZE for query optimization