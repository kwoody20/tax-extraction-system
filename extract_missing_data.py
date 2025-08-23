"""
Extract account numbers and addresses for properties with missing data
"""

import json
import pandas as pd
from datetime import datetime
import re
import time
from urllib.parse import urlparse, parse_qs
import requests
from bs4 import BeautifulSoup

# Load properties data
with open('properties_data.json', 'r') as f:
    data = json.load(f)

properties = data['properties']
df = pd.DataFrame(properties)

# Identify properties with missing data
missing_address = df[df['property_address'].isna() | (df['property_address'] == '')]
missing_account = df[df['account_number'].isna() | (df['account_number'] == '')]

# Combine to get properties missing either
missing_data = df[
    (df['property_address'].isna() | (df['property_address'] == '')) |
    (df['account_number'].isna() | (df['account_number'] == ''))
].copy()

print("📊 Properties with Missing Data")
print("=" * 60)
print(f"Total properties: {len(df)}")
print(f"Missing addresses: {len(missing_address)}")
print(f"Missing account numbers: {len(missing_account)}")
print(f"Properties needing updates: {len(missing_data)}")
print()

# Function to extract account number from URL
def extract_account_from_url(url):
    """Extract account number from tax bill URL"""
    if pd.isna(url) or url == '':
        return None
    
    parsed = urlparse(url)
    
    # Check query parameters
    params = parse_qs(parsed.query)
    
    # Common parameter names for account numbers
    account_params = ['account', 'acct', 'accountno', 'accountnumber', 'id', 
                     'parcel', 'parcelnumber', 'pin', 'property_id', 'prop_id',
                     'account_number', 'acct_no', 'acct_num']
    
    for param in account_params:
        if param in params:
            return params[param][0]
    
    # Check URL path for account patterns
    path = parsed.path
    
    # Look for patterns like /account/123456 or /property/123456
    patterns = [
        r'/account[s]?/([A-Z0-9\-]+)',
        r'/property/([A-Z0-9\-]+)',
        r'/parcel/([A-Z0-9\-]+)',
        r'/([0-9]{4,})',  # Just numbers in path
        r'/([A-Z0-9]{6,})'  # Alphanumeric codes
    ]
    
    for pattern in patterns:
        match = re.search(pattern, path, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

# Function to extract address from property name
def extract_address_from_name(name):
    """Extract address from property name"""
    if pd.isna(name):
        return None
    
    # Many property names contain the address at the beginning
    # Pattern: digits followed by street name, city, state zip
    
    # Remove business names in parentheses first
    clean_name = re.sub(r'\([^)]+\)', '', name).strip()
    
    # Common address patterns
    patterns = [
        # Standard US address
        r'^(\d+[\s\w\.\-,]+(?:STREET|ST|AVENUE|AVE|ROAD|RD|DRIVE|DR|LANE|LN|BOULEVARD|BLVD|PARKWAY|PKWY|COURT|CT|PLACE|PL|CIRCLE|CIR|HIGHWAY|HWY|FM \d+|SH \d+|US \d+|STATE HIGHWAY \d+)[^,]*)',
        # Address with city, state
        r'^(\d+[\s\w\.\-,]+,\s*[A-Z\s]+,\s*[A-Z]{2}\s*\d{5})',
        # Simple numbered address
        r'^(\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd))',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_name, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # If name starts with digits, it might be an address
    if re.match(r'^\d+\s+', clean_name):
        # Take everything before the first parenthesis or dash
        parts = re.split(r'[\(\-]', clean_name)
        if parts[0].strip():
            return parts[0].strip()
    
    return None

print("🔍 Attempting to Extract from Existing Data")
print("-" * 60)

# Try to extract missing data from existing fields
updates = []
extracted_accounts = 0
extracted_addresses = 0

for idx, row in missing_data.iterrows():
    update = {
        'id': row['id'],
        'property_name': row['property_name'],
        'current_account': row['account_number'],
        'current_address': row['property_address'],
        'new_account': None,
        'new_address': None,
        'source': None
    }
    
    # Try to extract account number from URL
    if pd.isna(row['account_number']) or row['account_number'] == '':
        account = extract_account_from_url(row.get('tax_bill_link'))
        if account:
            update['new_account'] = account
            update['source'] = 'Extracted from URL'
            extracted_accounts += 1
    
    # Try to extract address from property name
    if pd.isna(row['property_address']) or row['property_address'] == '':
        address = extract_address_from_name(row.get('property_name'))
        if address:
            update['new_address'] = address
            update['source'] = 'Extracted from property name'
            extracted_addresses += 1
    
    if update['new_account'] or update['new_address']:
        updates.append(update)
        print(f"✅ {row['property_name'][:50]}...")
        if update['new_account']:
            print(f"   Account: {update['new_account']}")
        if update['new_address']:
            print(f"   Address: {update['new_address'][:50]}...")

print()
print("📈 Extraction Results")
print("-" * 60)
print(f"Extracted {extracted_accounts} account numbers from URLs")
print(f"Extracted {extracted_addresses} addresses from property names")
print(f"Total properties with new data: {len(updates)}")

# Save updates to CSV
if updates:
    updates_df = pd.DataFrame(updates)
    filename = f"extracted_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    updates_df.to_csv(filename, index=False)
    print(f"\n✅ Updates saved to: {filename}")

# Identify properties that still need scraping
still_missing = missing_data.copy()
for update in updates:
    prop_id = update['id']
    if update['new_account']:
        still_missing.loc[still_missing['id'] == prop_id, 'account_number'] = update['new_account']
    if update['new_address']:
        still_missing.loc[still_missing['id'] == prop_id, 'property_address'] = update['new_address']

still_need_account = still_missing[still_missing['account_number'].isna() | (still_missing['account_number'] == '')]
still_need_address = still_missing[still_missing['property_address'].isna() | (still_missing['property_address'] == '')]

print("\n📋 Properties Still Needing Data")
print("-" * 60)
print(f"Still need account numbers: {len(still_need_account)}")
print(f"Still need addresses: {len(still_need_address)}")

if len(still_need_account) > 0 or len(still_need_address) > 0:
    # Prepare scraping list
    scrape_list = still_missing[
        (still_missing['account_number'].isna() | (still_missing['account_number'] == '')) |
        (still_missing['property_address'].isna() | (still_missing['property_address'] == ''))
    ][['id', 'property_name', 'jurisdiction', 'state', 'tax_bill_link', 'account_number', 'property_address']]
    
    scrape_filename = f"properties_to_scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    scrape_list.to_csv(scrape_filename, index=False)
    print(f"\n📄 Properties needing scraping saved to: {scrape_filename}")
    
    # Group by jurisdiction for efficient scraping
    print("\n🗺️ Properties by Jurisdiction (for scraping):")
    jurisdiction_counts = scrape_list['jurisdiction'].value_counts()
    for jur, count in jurisdiction_counts.head(10).items():
        print(f"  • {jur}: {count} properties")