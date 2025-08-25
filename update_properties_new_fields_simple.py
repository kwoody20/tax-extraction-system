#!/usr/bin/env python3
"""
Simple script to update properties with tax_due_date and paid_by from CSV.
Designed to work with production deployment.
"""

import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime
import logging

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Missing SUPABASE_URL or SUPABASE_KEY")
    exit(1)

# Create Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def update_properties_from_csv(csv_file):
    """Update properties with new fields from CSV."""
    
    # Read CSV
    logger.info(f"Reading CSV file: {csv_file}")
    df = pd.read_csv(csv_file)
    logger.info(f"Found {len(df)} properties in CSV")
    
    success_count = 0
    error_count = 0
    
    for index, row in df.iterrows():
        try:
            property_id = row.get('Property ID')
            if pd.isna(property_id):
                continue
            
            # Prepare update data
            update_data = {}
            
            # Handle tax_due_date
            if 'Tax Due Date' in row and pd.notna(row['Tax Due Date']):
                try:
                    # Parse and format date
                    date_val = pd.to_datetime(row['Tax Due Date'])
                    update_data['tax_due_date'] = date_val.strftime('%Y-%m-%d')
                except:
                    logger.warning(f"Could not parse date for property {property_id}: {row['Tax Due Date']}")
            
            # Handle paid_by
            if 'Paid By' in row and pd.notna(row['Paid By']):
                update_data['paid_by'] = str(row['Paid By']).strip()
            
            if update_data:
                # Update property in Supabase
                response = supabase.table('properties').update(update_data).eq('property_id', property_id).execute()
                
                # Supabase update returns 200 OK even without returning data
                # Assume success if no exception was raised
                success_count += 1
                logger.info(f"✅ Updated property {property_id}: {update_data}")
            
        except Exception as e:
            error_count += 1
            logger.error(f"Error updating property {property_id}: {e}")
    
    logger.info(f"\n✅ Successfully updated: {success_count} properties")
    logger.info(f"❌ Failed to update: {error_count} properties")
    
    return success_count, error_count

if __name__ == "__main__":
    csv_file = "properties-with-new-fields.csv"
    
    if not os.path.exists(csv_file):
        logger.error(f"CSV file not found: {csv_file}")
        exit(1)
    
    logger.info("Starting property update process...")
    success, errors = update_properties_from_csv(csv_file)
    
    if errors == 0:
        logger.info("✨ All properties updated successfully!")
    else:
        logger.warning(f"⚠️ Completed with {errors} errors")