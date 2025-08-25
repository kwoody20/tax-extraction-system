#!/usr/bin/env python3
"""
Script to update properties in Supabase with new Tax Due Date and Paid By fields.
Reads from properties-with-new-fields.csv and updates the database.
"""

import os
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
from typing import Dict, Any

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Supabase client with service key for admin operations
SUPABASE_URL = os.getenv("SUPABASE_URL")
# Try SUPABASE_SERVICE_ROLE_KEY first, then fall back to regular key
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables")
    logger.info("Note: This script requires SUPABASE_SERVICE_ROLE_KEY for admin operations")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
is_service_key = bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY"))
logger.info(f"Using Supabase client with {'service/role' if is_service_key else 'regular'} key")

def parse_date(date_str: str) -> str:
    """Parse date string and return ISO format."""
    if pd.isna(date_str) or not date_str:
        return None
    
    try:
        # Handle various date formats
        # Format 1: M/D/YY (e.g., 1/31/26)
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 3:
                month, day, year = parts
                # Convert 2-digit year to 4-digit
                if len(year) == 2:
                    year = '20' + year if int(year) < 50 else '19' + year
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # Try pandas parser as fallback
        dt = pd.to_datetime(date_str)
        return dt.date().isoformat()
    except Exception as e:
        logger.warning(f"Could not parse date '{date_str}': {e}")
        return None

def update_property(property_id: str, tax_due_date: str, paid_by: str) -> Dict[str, Any]:
    """Update a single property with new fields."""
    try:
        update_data = {}
        
        # Only add fields that have values
        if tax_due_date:
            update_data['tax_due_date'] = tax_due_date
        
        if paid_by:
            update_data['paid_by'] = paid_by
        
        if not update_data:
            return {"status": "skipped", "reason": "No data to update"}
        
        # Update the property
        response = supabase.table("properties").update(update_data).eq("property_id", property_id).execute()
        
        # Since Supabase doesn't return data by default on updates with Python client,
        # we'll consider it successful if no exception was raised
        return {"status": "success", "updated_fields": list(update_data.keys())}
            
    except Exception as e:
        return {"status": "error", "reason": str(e)}

def main():
    """Main function to process CSV and update database."""
    csv_file = "properties-with-new-fields.csv"
    
    # Check if file exists
    if not os.path.exists(csv_file):
        logger.error(f"CSV file '{csv_file}' not found")
        return
    
    # Read CSV
    logger.info(f"Reading CSV file: {csv_file}")
    df = pd.read_csv(csv_file)
    
    # Check required columns
    required_columns = ['Property ID', 'Tax Due Date', 'Paid By']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        logger.error(f"Missing required columns: {missing_columns}")
        return
    
    # Process each row
    total = len(df)
    success_count = 0
    skip_count = 0
    error_count = 0
    
    logger.info(f"Processing {total} properties...")
    
    for index, row in df.iterrows():
        property_id = row['Property ID']
        
        if pd.isna(property_id):
            logger.warning(f"Row {index + 1}: Skipping - no Property ID")
            skip_count += 1
            continue
        
        # Parse date
        tax_due_date = parse_date(row.get('Tax Due Date'))
        paid_by = row.get('Paid By') if pd.notna(row.get('Paid By')) else None
        
        # Update property
        result = update_property(property_id, tax_due_date, paid_by)
        
        if result['status'] == 'success':
            success_count += 1
            logger.info(f"Row {index + 1}: Updated property {property_id} - {result['updated_fields']}")
        elif result['status'] == 'skipped':
            skip_count += 1
            logger.debug(f"Row {index + 1}: Skipped property {property_id} - {result['reason']}")
        else:
            error_count += 1
            logger.error(f"Row {index + 1}: Failed to update property {property_id} - {result['reason']}")
        
        # Progress update every 10 rows
        if (index + 1) % 10 == 0:
            logger.info(f"Progress: {index + 1}/{total} processed")
    
    # Final summary
    logger.info("=" * 50)
    logger.info("Update Complete!")
    logger.info(f"Total properties: {total}")
    logger.info(f"Successfully updated: {success_count}")
    logger.info(f"Skipped (no data): {skip_count}")
    logger.info(f"Errors: {error_count}")
    
    # Show sample of updated data
    if success_count > 0:
        logger.info("\nVerifying updates...")
        # Query a few updated properties to verify
        sample_response = supabase.table("properties").select("property_id, property_name, tax_due_date, paid_by").limit(5).execute()
        if sample_response.data:
            logger.info("Sample of updated properties:")
            for prop in sample_response.data:
                if prop.get('tax_due_date') or prop.get('paid_by'):
                    logger.info(f"  - {prop['property_name']}: Due {prop.get('tax_due_date', 'N/A')}, Paid by {prop.get('paid_by', 'N/A')}")

if __name__ == "__main__":
    main()