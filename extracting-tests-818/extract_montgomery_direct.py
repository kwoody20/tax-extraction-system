#!/usr/bin/env python3
"""
Direct extraction script for Montgomery County tax data
Since we can fetch the HTML, parse it directly instead of using Playwright
"""

import requests
import pandas as pd
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urlparse, parse_qs
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_montgomery_data(url):
    """Extract tax data from Montgomery County URL"""
    
    try:
        # Make request with proper headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"HTTP {response.status_code} for {url}")
            return None
            
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract data from the page
        data = {}
        
        # Find all tables
        tables = soup.find_all('table')
        
        for table in tables:
            # Look for tax information in table cells
            cells = table.find_all('td')
            for i, cell in enumerate(cells):
                text = cell.get_text(strip=True)
                
                # Look for key patterns
                if 'Account #' in text or 'Account Number' in text:
                    if i + 1 < len(cells):
                        data['account_number'] = cells[i + 1].get_text(strip=True)
                        
                elif 'Owner Name' in text:
                    if i + 1 < len(cells):
                        data['owner_name'] = cells[i + 1].get_text(strip=True)
                        
                elif 'Property Address' in text or 'Situs' in text:
                    if i + 1 < len(cells):
                        data['property_address'] = cells[i + 1].get_text(strip=True)
                        
                elif 'Total Due' in text or 'Amount Due' in text:
                    if i + 1 < len(cells):
                        amount_text = cells[i + 1].get_text(strip=True)
                        # Extract dollar amount
                        match = re.search(r'\$[\d,]+\.?\d*', amount_text)
                        if match:
                            data['amount_due'] = match.group()
                            
                elif 'Tax Year' in text:
                    if i + 1 < len(cells):
                        data['tax_year'] = cells[i + 1].get_text(strip=True)
                        
                elif 'Current Taxes' in text or 'Current Amount' in text:
                    # Look for amount in same or next cell
                    amount_match = re.search(r'\$[\d,]+\.?\d*', text)
                    if amount_match:
                        data['current_taxes'] = amount_match.group()
                    elif i + 1 < len(cells):
                        next_text = cells[i + 1].get_text(strip=True)
                        amount_match = re.search(r'\$[\d,]+\.?\d*', next_text)
                        if amount_match:
                            data['current_taxes'] = amount_match.group()
        
        # Try to extract account number from URL if not found
        if 'account_number' not in data:
            parsed_url = urlparse(url)
            params = parse_qs(parsed_url.query)
            if 'can' in params:
                data['account_number'] = params['can'][0]
        
        # Look for all dollar amounts on the page
        all_amounts = re.findall(r'\$[\d,]+\.?\d*', response.text)
        if all_amounts:
            data['all_amounts_found'] = all_amounts[:10]  # First 10 amounts
            
        data['extraction_timestamp'] = datetime.now().isoformat()
        data['url'] = url
        
        return data
        
    except Exception as e:
        logger.error(f"Error extracting from {url}: {e}")
        return None

def process_montgomery_properties():
    """Process all Montgomery County properties"""
    
    logger.info("Starting Montgomery County direct extraction")
    
    # Read the CSV file
    try:
        df = pd.read_csv('completed-proptax-data.csv', encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv('completed-proptax-data.csv', encoding='latin-1')
    
    # Filter Montgomery County properties
    montgomery_df = df[
        (df['Jurisdiction'] == 'Montgomery') & 
        (df['Tax Bill Link'].notna()) &
        (~df['Property Type'].isin(['entity', 'sub-entity']))
    ]
    
    logger.info(f"Processing {len(montgomery_df)} Montgomery County properties")
    
    results = []
    
    for idx, row in montgomery_df.iterrows():
        property_name = row['Property Name']
        url = row['Tax Bill Link']
        
        logger.info(f"Extracting: {property_name}")
        
        data = extract_montgomery_data(url)
        
        if data:
            data['property_id'] = row['Property ID']
            data['property_name'] = property_name
            data['extraction_status'] = 'success'
            logger.info(f"  ✓ Extracted: {data.get('amount_due', 'No amount found')}")
        else:
            data = {
                'property_id': row['Property ID'],
                'property_name': property_name,
                'url': url,
                'extraction_status': 'failed',
                'extraction_timestamp': datetime.now().isoformat()
            }
            logger.warning(f"  ✗ Failed to extract data")
            
        results.append(data)
    
    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv('montgomery_direct_extraction.csv', index=False)
    
    with open('montgomery_direct_extraction.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Summary
    successful = sum(1 for r in results if r['extraction_status'] == 'success')
    failed = sum(1 for r in results if r['extraction_status'] == 'failed')
    
    logger.info("\n" + "="*60)
    logger.info("Extraction Complete:")
    logger.info(f"  Successful: {successful}")
    logger.info(f"  Failed: {failed}")
    logger.info(f"  Total: {len(results)}")
    logger.info("="*60)
    
    return results

if __name__ == "__main__":
    results = process_montgomery_properties()
    
    # Display sample results
    print("\nSample Results:")
    for result in results[:3]:
        print(f"\nProperty: {result['property_name']}")
        print(f"  Status: {result['extraction_status']}")
        if result['extraction_status'] == 'success':
            print(f"  Account: {result.get('account_number', 'N/A')}")
            print(f"  Amount Due: {result.get('amount_due', 'N/A')}")
            print(f"  Current Taxes: {result.get('current_taxes', 'N/A')}")
            if 'all_amounts_found' in result:
                print(f"  All amounts: {', '.join(result['all_amounts_found'][:5])}")