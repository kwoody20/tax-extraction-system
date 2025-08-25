#!/usr/bin/env python3
"""
Script to apply the new migration to add tax_due_date and paid_by columns to the database.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

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
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_KEY"))

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logger.error("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables")
    exit(1)

def apply_migration():
    """Apply the migration to add new columns."""
    
    # Read the migration file
    migration_file = "supabase/migrations/012_add_tax_due_date_and_paid_by.sql"
    
    if not os.path.exists(migration_file):
        logger.error(f"Migration file not found: {migration_file}")
        return False
    
    with open(migration_file, 'r') as f:
        migration_sql = f.read()
    
    logger.info("Migration SQL to be applied:")
    logger.info("-" * 50)
    logger.info(migration_sql)
    logger.info("-" * 50)
    
    # Note: Supabase Python client doesn't have direct SQL execution
    # You'll need to run this via Supabase Dashboard SQL Editor or CLI
    
    logger.info("\nTo apply this migration:")
    logger.info("1. Go to your Supabase Dashboard: https://app.supabase.com")
    logger.info("2. Navigate to SQL Editor")
    logger.info("3. Copy and paste the migration SQL above")
    logger.info("4. Click 'Run' to execute")
    logger.info("\nAlternatively, use Supabase CLI:")
    logger.info("supabase db push")
    
    return True

if __name__ == "__main__":
    logger.info("Preparing to apply database migration...")
    
    if apply_migration():
        logger.info("\nNext steps:")
        logger.info("1. Apply the migration using Supabase Dashboard or CLI")
        logger.info("2. Run: python update_properties_with_new_fields.py")
        logger.info("   This will populate the new fields from the CSV file")
        logger.info("3. Restart the API and dashboard to see the new fields")
    else:
        logger.error("Migration preparation failed")