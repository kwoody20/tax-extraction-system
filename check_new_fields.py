#!/usr/bin/env python3
"""
Check if the new fields were successfully updated in Supabase.
"""

import os
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

# Get a few properties to check the new fields
logger.info("Checking properties for new fields...")

try:
    # Get first 10 properties
    response = supabase.table('properties').select("property_id, property_name, tax_due_date, paid_by").limit(10).execute()
    
    if response.data:
        logger.info(f"\nFound {len(response.data)} properties:")
        
        has_tax_due_date = False
        has_paid_by = False
        
        for prop in response.data:
            logger.info(f"\nProperty: {prop.get('property_name', 'N/A')}")
            logger.info(f"  ID: {prop.get('property_id')}")
            logger.info(f"  Tax Due Date: {prop.get('tax_due_date', 'NULL')}")
            logger.info(f"  Paid By: {prop.get('paid_by', 'NULL')}")
            
            if prop.get('tax_due_date'):
                has_tax_due_date = True
            if prop.get('paid_by'):
                has_paid_by = True
        
        logger.info("\n" + "="*50)
        if has_tax_due_date or has_paid_by:
            logger.info("✅ Some properties have the new field data!")
        else:
            logger.info("⚠️  The columns exist but no data is populated yet")
            logger.info("This might mean:")
            logger.info("1. The migration hasn't been run in Supabase yet")
            logger.info("2. The update script needs to be fixed")
    else:
        logger.warning("No properties found in database")
        
except Exception as e:
    logger.error(f"Error checking properties: {e}")
    logger.info("\nThis error might mean the columns don't exist yet.")
    logger.info("Please run the migration in Supabase SQL Editor first.")