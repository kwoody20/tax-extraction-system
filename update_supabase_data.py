"""
Update Supabase with extracted account numbers and compile all updates
"""

import pandas as pd
import json
from datetime import datetime
import os
from supabase import create_client, Client

# Load environment variables
SUPABASE_URL = "https://klscgjbachumeojhxyno.supabase.co"
SUPABASE_KEY = None

# Try to load from .env file
try:
    with open('.env', 'r') as f:
        for line in f:
            if 'SUPABASE_SERVICE_ROLE_KEY=' in line:
                SUPABASE_KEY = line.split('=', 1)[1].strip().strip('"').strip("'")
                break
except:
    pass

if not SUPABASE_KEY:
    print("❌ Error: SUPABASE_SERVICE_ROLE_KEY not found")
    exit(1)

# Initialize Supabase client with service role key for admin access
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("📊 Compiling All Updates for Supabase")
print("=" * 60)

# Load the extracted account numbers
extracted_df = pd.read_csv('extracted_data_20250823_134809.csv')

print(f"\n✅ Found {len(extracted_df)} properties with extracted account numbers")

# Prepare updates
updates = []
update_count = 0
address_count = 0
account_count = 0

for _, row in extracted_df.iterrows():
    update_data = {}
    
    # Add account number if found
    if pd.notna(row.get('new_account')) and row['new_account'] != '':
        update_data['account_number'] = str(row['new_account'])
        account_count += 1
    
    # Add address if found (though we didn't find many)
    if pd.notna(row.get('new_address')) and row['new_address'] != '':
        update_data['property_address'] = str(row['new_address'])
        address_count += 1
    
    if update_data:
        updates.append({
            'id': row['id'],
            'property_name': row['property_name'],
            'updates': update_data
        })
        update_count += 1

print(f"\n📝 Updates to Apply:")
print(f"  • Properties to update: {update_count}")
print(f"  • Account numbers to add: {account_count}")
print(f"  • Addresses to add: {address_count}")

if updates:
    print("\n🔄 Applying Updates to Supabase...")
    print("-" * 60)
    
    success_count = 0
    error_count = 0
    errors = []
    
    for update in updates:
        try:
            # Update the property in Supabase
            response = supabase.table('properties').update(
                update['updates']
            ).eq('id', update['id']).execute()
            
            if response.data:
                success_count += 1
                print(f"✅ Updated: {update['property_name'][:50]}...")
                if 'account_number' in update['updates']:
                    print(f"   Account: {update['updates']['account_number']}")
                if 'property_address' in update['updates']:
                    print(f"   Address: {update['updates']['property_address'][:50]}")
            else:
                error_count += 1
                errors.append({
                    'property': update['property_name'],
                    'error': 'No response data'
                })
                
        except Exception as e:
            error_count += 1
            errors.append({
                'property': update['property_name'],
                'error': str(e)
            })
            print(f"❌ Error updating {update['property_name'][:40]}: {e}")
    
    print("\n" + "=" * 60)
    print("\n📊 Update Summary")
    print("-" * 60)
    print(f"✅ Successfully updated: {success_count} properties")
    print(f"❌ Failed updates: {error_count}")
    
    if errors:
        print("\n⚠️ Errors encountered:")
        for error in errors[:5]:
            print(f"  • {error['property'][:40]}: {error['error'][:50]}")
    
    # Save update log
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'total_updates': update_count,
        'successful': success_count,
        'failed': error_count,
        'account_numbers_added': account_count,
        'addresses_added': address_count,
        'errors': errors
    }
    
    log_filename = f"supabase_update_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_filename, 'w') as f:
        json.dump(log_data, f, indent=2)
    
    print(f"\n📄 Update log saved to: {log_filename}")
    
    # Verify updates
    print("\n🔍 Verifying Updates...")
    try:
        # Get fresh data from Supabase
        response = supabase.table('properties').select("*").execute()
        properties = response.data
        
        if properties:
            df_updated = pd.DataFrame(properties)
            
            # Check account number completeness
            account_complete = df_updated['account_number'].notna().sum()
            address_complete = (df_updated['property_address'].notna() & 
                               (df_updated['property_address'] != '')).sum()
            
            print(f"\n📈 Updated Database Status:")
            print(f"  • Total properties: {len(df_updated)}")
            print(f"  • Properties with account numbers: {account_complete}/{len(df_updated)} ({account_complete/len(df_updated)*100:.1f}%)")
            print(f"  • Properties with addresses: {address_complete}/{len(df_updated)} ({address_complete/len(df_updated)*100:.1f}%)")
            
            # Calculate improvement
            print(f"\n📊 Improvement:")
            print(f"  • Account numbers: +{account_count} (from 55 to {account_complete})")
            print(f"  • Addresses: +{address_count} (from 50 to {address_complete})")
            
    except Exception as e:
        print(f"❌ Error verifying updates: {e}")

else:
    print("\n⚠️ No updates to apply")

print("\n✅ Update process complete!")