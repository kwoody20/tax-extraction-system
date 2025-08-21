#!/usr/bin/env python3
"""
Test script to identify Maricopa County form elements
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def analyze_maricopa_page():
    """Analyze the Maricopa County Treasurer page to find form elements"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # Show browser for debugging
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = await browser.new_page()
        
        try:
            print("Navigating to Maricopa County Treasurer's Office...")
            await page.goto('https://treasurer.maricopa.gov/', wait_until='networkidle')
            
            print("\nWaiting for page to fully load...")
            await page.wait_for_timeout(3000)
            
            # Find all input elements
            print("\n=== ANALYZING INPUT ELEMENTS ===")
            inputs = await page.query_selector_all('input')
            
            for i, input_elem in enumerate(inputs):
                try:
                    input_type = await input_elem.get_attribute('type')
                    input_name = await input_elem.get_attribute('name')
                    input_id = await input_elem.get_attribute('id')
                    input_placeholder = await input_elem.get_attribute('placeholder')
                    input_class = await input_elem.get_attribute('class')
                    is_visible = await input_elem.is_visible()
                    
                    if input_type not in ['hidden', 'submit'] and is_visible:
                        print(f"\nInput #{i}:")
                        print(f"  Type: {input_type}")
                        print(f"  Name: {input_name}")
                        print(f"  ID: {input_id}")
                        print(f"  Placeholder: {input_placeholder}")
                        print(f"  Class: {input_class}")
                        print(f"  Visible: {is_visible}")
                        
                        # Check if it's the parcel number input
                        if input_name or input_id or input_placeholder:
                            if any(term in str(val).lower() for val in [input_name, input_id, input_placeholder] 
                                   for term in ['parcel', 'number', 'search']):
                                print("  *** LIKELY PARCEL NUMBER INPUT ***")
                except:
                    pass
            
            # Look for the search button
            print("\n=== ANALYZING BUTTONS ===")
            buttons = await page.query_selector_all('button, input[type="submit"], input[type="button"], a.button, .button')
            
            for i, button in enumerate(buttons):
                try:
                    button_text = await button.text_content()
                    button_value = await button.get_attribute('value')
                    button_type = await button.get_attribute('type')
                    button_class = await button.get_attribute('class')
                    is_visible = await button.is_visible()
                    
                    if is_visible and (button_text or button_value):
                        print(f"\nButton #{i}:")
                        print(f"  Text: {button_text}")
                        print(f"  Value: {button_value}")
                        print(f"  Type: {button_type}")
                        print(f"  Class: {button_class}")
                        
                        if any(term in str(val).lower() for val in [button_text, button_value] 
                               for term in ['search', 'submit', 'go', 'find']):
                            print("  *** LIKELY SEARCH BUTTON ***")
                except:
                    pass
            
            # Try to find the parcel search form specifically
            print("\n=== LOOKING FOR PARCEL SEARCH FORM ===")
            
            # Method 1: Look for text input with nearby "Parcel" label
            parcel_labels = await page.query_selector_all('text=/parcel/i')
            for label in parcel_labels:
                print(f"\nFound 'Parcel' text element")
                # Find nearby input
                parent = await label.query_selector('xpath=..')
                if parent:
                    nearby_input = await parent.query_selector('input[type="text"]')
                    if nearby_input:
                        input_name = await nearby_input.get_attribute('name')
                        input_id = await nearby_input.get_attribute('id')
                        print(f"  Found nearby input - Name: {input_name}, ID: {input_id}")
            
            # Method 2: Look for forms
            print("\n=== ANALYZING FORMS ===")
            forms = await page.query_selector_all('form')
            for i, form in enumerate(forms):
                form_action = await form.get_attribute('action')
                form_method = await form.get_attribute('method')
                form_name = await form.get_attribute('name')
                print(f"\nForm #{i}:")
                print(f"  Action: {form_action}")
                print(f"  Method: {form_method}")
                print(f"  Name: {form_name}")
                
                # Get inputs within this form
                form_inputs = await form.query_selector_all('input[type="text"]')
                for input_elem in form_inputs:
                    input_name = await input_elem.get_attribute('name')
                    input_id = await input_elem.get_attribute('id')
                    print(f"  Contains input - Name: {input_name}, ID: {input_id}")
            
            # Take a screenshot for reference
            await page.screenshot(path='maricopa_page.png')
            print("\nScreenshot saved as maricopa_page.png")
            
            print("\n=== TESTING PARCEL NUMBER ENTRY ===")
            # Try to enter a test parcel number
            test_parcel = "214-05-025A"
            
            # Try different selectors
            selectors_to_try = [
                'input[type="text"]:visible',
                'input#parcelNumber',
                'input[name*="parcel"]',
                'input[placeholder*="Parcel"]',
                '.parcel-search input',
                'input.form-control',
                'input[type="text"]'
            ]
            
            for selector in selectors_to_try:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        print(f"\nFound input with selector: {selector}")
                        await element.fill(test_parcel)
                        print(f"  Successfully filled with: {test_parcel}")
                        await page.wait_for_timeout(1000)
                        
                        # Try to submit
                        await page.keyboard.press('Enter')
                        print("  Pressed Enter")
                        await page.wait_for_timeout(3000)
                        
                        # Check if navigation occurred
                        new_url = page.url
                        print(f"  Current URL: {new_url}")
                        
                        break
                except Exception as e:
                    print(f"\n  Failed with selector {selector}: {e}")
            
            input("\nPress Enter to close the browser...")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(analyze_maricopa_page())