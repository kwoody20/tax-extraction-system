#!/usr/bin/env python3
"""
Debug script to see what's on the Maricopa results page
"""

import asyncio
from playwright.async_api import async_playwright

async def debug_maricopa():
    """Debug what's on the results page after searching"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            # Navigate to the site
            await page.goto('https://treasurer.maricopa.gov/')
            await page.wait_for_selector('#txtParcelNumBook')
            
            # Enter a test parcel number
            parcel = "214-05-025A"
            parts = parcel.split('-')
            
            await page.fill('#txtParcelNumBook', parts[0])
            await page.fill('#txtParcelNumMap', parts[1])
            await page.fill('#txtParcelNumItem', parts[2][:-1])
            await page.fill('#txtParcelNumSplit', parts[2][-1])
            
            # Click search
            await page.click('a.button:has-text("Search")')
            
            # Wait for results
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)
            
            print(f"Current URL: {page.url}")
            
            # Get all text content
            text_content = await page.text_content('body')
            print("\n=== PAGE CONTENT ===")
            print(text_content[:2000])
            
            # Look for links to property details
            print("\n=== LINKS ON PAGE ===")
            links = await page.query_selector_all('a')
            for link in links:
                href = await link.get_attribute('href')
                text = await link.text_content()
                if href and ('property' in href.lower() or 'parcel' in href.lower() or 'account' in href.lower()):
                    print(f"Link: {text.strip()} -> {href}")
            
            # Look for any clickable rows or property links
            print("\n=== CHECKING FOR CLICKABLE ELEMENTS ===")
            
            # Try clicking on the parcel number if it appears as a link
            parcel_link = await page.query_selector(f'a:has-text("{parcel}")')
            if parcel_link:
                print(f"Found parcel link, clicking...")
                await parcel_link.click()
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(3000)
                
                print(f"\nNew URL after click: {page.url}")
                
                # Now look for tax information
                print("\n=== TAX INFORMATION ===")
                
                # Look for amounts
                elements_with_dollar = await page.query_selector_all('*:has-text("$")')
                for elem in elements_with_dollar[:10]:  # First 10 elements with $
                    text = await elem.text_content()
                    if text and len(text) < 200:
                        print(f"Amount found: {text.strip()}")
            
            input("\nPress Enter to close browser...")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_maricopa())