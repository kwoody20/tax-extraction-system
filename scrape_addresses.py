"""
Scrape addresses from tax bill websites
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urlparse
import json
from datetime import datetime

# Load properties that need scraping
scrape_df = pd.read_csv('properties_to_scrape_20250823_134809.csv')

print("🔍 Starting Address Scraping")
print("=" * 60)
print(f"Properties to process: {len(scrape_df)}")
print()

# Results storage
results = []

def extract_address_from_page(url, jurisdiction):
    """Extract address from tax bill page"""
    try:
        # Add headers to avoid blocking
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()
        
        # Common patterns for addresses on tax pages
        address_patterns = [
            # Look for "Property Address:" labels
            r'Property Address[:\s]+([^\n]+)',
            r'Location[:\s]+([^\n]+)',
            r'Situs Address[:\s]+([^\n]+)',
            r'Physical Address[:\s]+([^\n]+)',
            # Standard address pattern
            r'(\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)[^\n]*)',
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                address = match.group(1).strip()
                # Clean up the address
                address = re.sub(r'\s+', ' ', address)  # Multiple spaces to single
                if len(address) > 10 and len(address) < 200:  # Sanity check
                    return address
        
        return None
        
    except Exception as e:
        print(f"  Error: {e}")
        return None

def process_montgomery_properties(properties):
    """Special handling for Montgomery County properties"""
    results = []
    base_url = "https://actweb.acttax.com/act_webdev/montgomery/showdetail2.jsp"
    
    for _, prop in properties.iterrows():
        # Extract account from the URL or use existing
        account = prop['account_number']
        if pd.isna(account) or account == '':
            # Try to extract from URL
            if 'account=' in str(prop['tax_bill_link']):
                account = prop['tax_bill_link'].split('account=')[1].split('&')[0]
        
        if account and account != 'montgomery':
            try:
                url = f"{base_url}?account={account}"
                response = requests.get(url, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for property details table
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        for i, cell in enumerate(cells):
                            if 'Property' in cell.get_text() and i + 1 < len(cells):
                                address = cells[i + 1].get_text().strip()
                                if address and len(address) > 5:
                                    results.append({
                                        'id': prop['id'],
                                        'property_name': prop['property_name'],
                                        'found_address': address,
                                        'found_account': account,
                                        'source': 'Montgomery scraper'
                                    })
                                    print(f"✅ Found: {address[:50]}")
                                    break
                                    
            except Exception as e:
                print(f"  Error processing Montgomery property: {e}")
    
    return results

def process_harris_properties(properties):
    """Special handling for Harris County properties"""
    results = []
    
    for _, prop in properties.iterrows():
        url = prop['tax_bill_link']
        if pd.notna(url):
            try:
                response = requests.get(url, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Harris County specific selectors
                address_elem = soup.find('span', {'id': re.compile('PropertyAddress')})
                if not address_elem:
                    address_elem = soup.find('div', text=re.compile('Property Address'))
                    
                if address_elem:
                    # Get the next element or parent's text
                    address = address_elem.get_text().replace('Property Address:', '').strip()
                    if not address:
                        next_elem = address_elem.find_next_sibling()
                        if next_elem:
                            address = next_elem.get_text().strip()
                    
                    if address and len(address) > 5:
                        results.append({
                            'id': prop['id'],
                            'property_name': prop['property_name'],
                            'found_address': address,
                            'found_account': prop['account_number'],
                            'source': 'Harris scraper'
                        })
                        print(f"✅ Found: {address[:50]}")
                        
            except Exception as e:
                print(f"  Error processing Harris property: {e}")
    
    return results

# Process by jurisdiction
print("📍 Processing by Jurisdiction")
print("-" * 60)

# Montgomery County
montgomery_props = scrape_df[scrape_df['jurisdiction'] == 'Montgomery']
if len(montgomery_props) > 0:
    print(f"\n🏛️ Montgomery County ({len(montgomery_props)} properties)")
    montgomery_results = process_montgomery_properties(montgomery_props)
    results.extend(montgomery_results)
    time.sleep(1)  # Be polite

# Harris County  
harris_props = scrape_df[scrape_df['jurisdiction'] == 'Harris']
if len(harris_props) > 0:
    print(f"\n🏛️ Harris County ({len(harris_props)} properties)")
    harris_results = process_harris_properties(harris_props)
    results.extend(harris_results)
    time.sleep(1)

# Generic processing for other jurisdictions
other_props = scrape_df[~scrape_df['jurisdiction'].isin(['Montgomery', 'Harris'])]
if len(other_props) > 0:
    print(f"\n🏛️ Other Jurisdictions ({len(other_props)} properties)")
    for _, prop in other_props.head(10).iterrows():  # Limit to avoid rate limiting
        url = prop['tax_bill_link']
        if pd.notna(url):
            print(f"  Checking: {prop['property_name'][:40]}...")
            address = extract_address_from_page(url, prop['jurisdiction'])
            if address:
                results.append({
                    'id': prop['id'],
                    'property_name': prop['property_name'],
                    'found_address': address,
                    'found_account': prop['account_number'],
                    'source': 'Generic scraper'
                })
                print(f"  ✅ Found: {address[:50]}")
            time.sleep(0.5)  # Rate limiting

print()
print("=" * 60)
print(f"\n📊 Scraping Results")
print("-" * 60)
print(f"Total addresses found: {len(results)}")

if results:
    # Save results
    results_df = pd.DataFrame(results)
    filename = f"scraped_addresses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    results_df.to_csv(filename, index=False)
    print(f"✅ Results saved to: {filename}")
    
    # Show sample
    print("\n📋 Sample Results:")
    for result in results[:5]:
        print(f"  • {result['property_name'][:40]}...")
        print(f"    Address: {result['found_address']}")
        print()