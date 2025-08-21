#!/usr/bin/env python3
"""Direct test for Wayne County with specific selectors"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import re

def parse_currency(text):
    """Parse currency text to float"""
    if not text:
        return None
    try:
        # Remove currency symbols, commas, and extra text
        cleaned = re.sub(r'[^\d.]', '', text)
        return float(cleaned) if cleaned else None
    except:
        return None

# Setup driver
options = Options()
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(options=options)

try:
    url = 'https://pwa.waynegov.com/PublicWebAccess/BillDetails.aspx?BillPk=2454000'
    print(f"Navigating to: {url}")
    driver.get(url)
    time.sleep(3)
    
    # Get page source for debugging
    page_text = driver.find_element(By.TAG_NAME, 'body').text
    
    # Look for Total Billed in the page text
    if 'Total Billed:' in page_text:
        print("Found 'Total Billed:' in page text")
        # Extract the amount after "Total Billed:"
        lines = page_text.split('\n')
        for i, line in enumerate(lines):
            if 'Total Billed:' in line:
                print(f"Line with Total Billed: {line}")
                # The amount might be on the same line or next line
                if '$' in line:
                    amount_str = line.split('$')[-1].strip()
                    amount = parse_currency('$' + amount_str)
                    print(f"Found amount on same line: ${amount}")
                elif i + 1 < len(lines) and '$' in lines[i + 1]:
                    amount = parse_currency(lines[i + 1])
                    print(f"Found amount on next line: ${amount}")
    
    # Try to find it in specific cells
    print("\nLooking for all text containing dollar amounts...")
    elements_with_dollars = driver.find_elements(By.XPATH, "//*[contains(text(), '$')]")
    for elem in elements_with_dollars[:20]:  # First 20 to avoid too much output
        text = elem.text.strip()
        if text and len(text) < 100:  # Skip very long texts
            print(f"  Found: {text}")
            if '8,314' in text or '8314' in text:
                print(f"  ^^^ This looks like our tax amount!")
    
    # Look specifically in the area after "Total Assessed Value"
    print("\nLooking after Total Assessed Value...")
    try:
        # Find all td elements
        all_tds = driver.find_elements(By.TAG_NAME, 'td')
        found_assessed = False
        for td in all_tds:
            text = td.text.strip()
            if 'Total Assessed Value' in text:
                found_assessed = True
                print(f"Found Total Assessed Value cell")
            elif found_assessed and text:
                print(f"  Next cell: {text}")
                if 'Total Billed' in text or '$8,314' in text:
                    print(f"  ^^^ Found Total Billed!")
                    break
    except Exception as e:
        print(f"Error: {e}")
    
finally:
    driver.quit()