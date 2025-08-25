#!/usr/bin/env python3
"""
Update properties with new fields by matching on property name.
"""

import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Missing SUPABASE_URL or SUPABASE_KEY")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Read CSV
logger.info("Reading CSV file...")
df = pd.read_csv("properties-with-new-fields.csv")
logger.info(f"Found {len(df)} properties in CSV")

# Get all properties from database
logger.info("Fetching properties from database...")
response = supabase.table('properties').select("property_id, property_name").execute()
db_properties = {prop['property_name']: prop['property_id'] for prop in response.data}
logger.info(f"Found {len(db_properties)} properties in database")

success_count = 0
not_found_count = 0
error_count = 0

for index, row in df.iterrows():
    try:
        # Get property name from CSV
        property_name = row.get('Property Name (Mapping)')
        if pd.isna(property_name):
            continue
        
        # Find matching property ID in database
        if property_name not in db_properties:
            not_found_count += 1
            logger.warning(f"Property not found in database: {property_name}")
            continue
        
        property_id = db_properties[property_name]
        
        # Prepare update data
        update_data = {}
        
        # Handle tax_due_date
        if 'Tax Due Date' in row and pd.notna(row['Tax Due Date']):
            try:
                date_val = pd.to_datetime(row['Tax Due Date'])
                update_data['tax_due_date'] = date_val.strftime('%Y-%m-%d')
            except:
                logger.warning(f"Could not parse date for {property_name}: {row['Tax Due Date']}")
        
        # Handle paid_by
        if 'Paid By' in row and pd.notna(row['Paid By']):
            update_data['paid_by'] = str(row['Paid By']).strip()
        
        if update_data:
            # Update property in Supabase
            response = supabase.table('properties').update(update_data).eq('property_id', property_id).execute()
            success_count += 1
            logger.info(f"✅ Updated {property_name}: {update_data}")
        
    except Exception as e:
        error_count += 1
        logger.error(f"Error processing row {index}: {e}")

logger.info(f"\n{'='*50}")
logger.info(f"✅ Successfully updated: {success_count} properties")
logger.info(f"⚠️  Not found in database: {not_found_count} properties")
logger.info(f"❌ Errors: {error_count}")

if success_count > 0:
    logger.info("\n🎉 Updates applied! Refresh your Streamlit app to see the new data.")