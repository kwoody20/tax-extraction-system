#!/usr/bin/env python3
"""
Investigation script for Montgomery County tax websites
Analyzes why the sites are timing out and what content they return
"""

import requests
import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import json
import time
from urllib.parse import urlparse, parse_qs
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('montgomery_investigation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_direct_request(url):
    """Test direct HTTP request to the URL"""
    logger.info(f"Testing direct HTTP request to: {url}")
    
    try:
        # Test with different headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Final URL: {response.url}")
        logger.info(f"Response Headers: {dict(response.headers)}")
        logger.info(f"Content Length: {len(response.content)} bytes")
        
        # Check content type
        content_type = response.headers.get('Content-Type', '')
        logger.info(f"Content Type: {content_type}")
        
        # Save response for analysis
        with open('montgomery_response.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        logger.info("Saved response to montgomery_response.html")
        
        # Check for common issues
        if 'maintenance' in response.text.lower():
            logger.warning("Site appears to be under maintenance")
        if 'error' in response.text.lower():
            logger.warning("Response contains error messages")
        if len(response.text) < 1000:
            logger.warning(f"Response seems too short: {len(response.text)} characters")
            
        # Look for specific patterns
        if '<body' not in response.text.lower():
            logger.error("No <body> tag found in response")
        if 'javascript' in response.text.lower():
            logger.info("Page uses JavaScript - may need browser rendering")
            
        return True
        
    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        return False
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

async def test_playwright_browser(url):
    """Test with Playwright browser automation"""
    logger.info(f"Testing with Playwright browser: {url}")
    
    async with async_playwright() as p:
        browser = None
        try:
            # Try different browser configurations
            browser = await p.chromium.launch(
                headless=False,  # Run with visible browser for debugging
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            )
            
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = await context.new_page()
            
            # Enable console logging
            page.on("console", lambda msg: logger.info(f"Browser console: {msg.text}"))
            page.on("pageerror", lambda exc: logger.error(f"Page error: {exc}"))
            
            logger.info("Navigating to URL...")
            
            # Try different wait strategies
            try:
                # Strategy 1: Wait for navigation
                response = await page.goto(url, wait_until='networkidle', timeout=60000)
                logger.info(f"Navigation completed with status: {response.status}")
                
            except Exception as e:
                logger.warning(f"NetworkIdle failed: {e}, trying domcontentloaded...")
                response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                
            # Get page info
            title = await page.title()
            logger.info(f"Page title: {title}")
            
            # Check current URL (might be redirected)
            current_url = page.url
            logger.info(f"Current URL: {current_url}")
            
            # Try to wait for body
            try:
                await page.wait_for_selector('body', timeout=5000)
                logger.info("Body element found")
                
                # Check body visibility
                is_visible = await page.is_visible('body')
                logger.info(f"Body visibility: {is_visible}")
                
                # Get body attributes
                body_attrs = await page.evaluate('''() => {
                    const body = document.body;
                    return {
                        display: window.getComputedStyle(body).display,
                        visibility: window.getComputedStyle(body).visibility,
                        opacity: window.getComputedStyle(body).opacity,
                        className: body.className,
                        id: body.id,
                        innerHTML_length: body.innerHTML.length
                    }
                }''')
                logger.info(f"Body attributes: {body_attrs}")
                
            except Exception as e:
                logger.error(f"Failed to find body: {e}")
                
            # Get page content
            content = await page.content()
            logger.info(f"Page content length: {len(content)}")
            
            # Save screenshot
            await page.screenshot(path='montgomery_screenshot.png', full_page=True)
            logger.info("Screenshot saved to montgomery_screenshot.png")
            
            # Save page content
            with open('montgomery_playwright.html', 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info("Page content saved to montgomery_playwright.html")
            
            # Check for iframes
            frames = page.frames
            logger.info(f"Number of frames: {len(frames)}")
            
            # Look for specific Montgomery County elements
            selectors_to_check = [
                'body',
                '#content',
                '.container',
                'table',
                'form',
                'input',
                '[name="can"]',
                '.tax-info',
                '#tax-details'
            ]
            
            for selector in selectors_to_check:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        logger.info(f"Found {count} elements matching '{selector}'")
                except:
                    pass
                    
            return True
            
        except Exception as e:
            logger.error(f"Playwright error: {e}")
            return False
        finally:
            if browser:
                await browser.close()

async def analyze_montgomery_sites():
    """Analyze all Montgomery County URLs from the CSV"""
    logger.info("Starting Montgomery County site investigation")
    
    # Read the CSV file with encoding handling
    try:
        df = pd.read_csv('completed-proptax-data.csv', encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv('completed-proptax-data.csv', encoding='latin-1')
    
    # Filter Montgomery County properties
    montgomery_df = df[df['Jurisdiction'] == 'Montgomery']
    logger.info(f"Found {len(montgomery_df)} Montgomery County properties")
    
    # Get unique URLs
    montgomery_urls = montgomery_df['Tax Bill Link'].dropna().unique()
    logger.info(f"Found {len(montgomery_urls)} unique Montgomery URLs")
    
    results = []
    
    # Test a sample of URLs
    for i, url in enumerate(montgomery_urls[:3]):  # Test first 3 URLs
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing URL {i+1}/{len(montgomery_urls[:3])}: {url}")
        logger.info('='*60)
        
        result = {
            'url': url,
            'direct_request': test_direct_request(url),
            'playwright': await test_playwright_browser(url)
        }
        results.append(result)
        
        # Wait between tests
        time.sleep(2)
    
    # Save results
    with open('montgomery_investigation_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("\n" + "="*60)
    logger.info("Investigation Summary:")
    logger.info("="*60)
    
    for result in results:
        logger.info(f"URL: {result['url']}")
        logger.info(f"  Direct Request: {'✓' if result['direct_request'] else '✗'}")
        logger.info(f"  Playwright: {'✓' if result['playwright'] else '✗'}")
    
    return results

async def test_alternative_approach():
    """Test alternative approaches for Montgomery County"""
    logger.info("\nTesting alternative approaches...")
    
    # Test base URL
    base_url = "https://actweb.acttax.com/act_webdev/montgomery/"
    
    logger.info(f"Testing base URL: {base_url}")
    test_direct_request(base_url)
    
    # Test search page
    search_url = "https://actweb.acttax.com/act_webdev/montgomery/search.jsp"
    logger.info(f"\nTesting search page: {search_url}")
    test_direct_request(search_url)
    
    # Test with curl command
    import subprocess
    logger.info("\nTesting with curl command...")
    
    test_url = "https://actweb.acttax.com/act_webdev/montgomery/showdetail2.jsp?can=0003510100300&ownerno=0"
    curl_cmd = f'curl -L -H "User-Agent: Mozilla/5.0" "{test_url}"'
    
    try:
        result = subprocess.run(curl_cmd, shell=True, capture_output=True, text=True, timeout=30)
        logger.info(f"Curl exit code: {result.returncode}")
        logger.info(f"Response length: {len(result.stdout)} characters")
        
        with open('montgomery_curl.html', 'w') as f:
            f.write(result.stdout)
        logger.info("Curl response saved to montgomery_curl.html")
        
    except subprocess.TimeoutExpired:
        logger.error("Curl command timed out")
    except Exception as e:
        logger.error(f"Curl error: {e}")

async def main():
    """Main investigation function"""
    logger.info("Starting Montgomery County Tax Site Investigation")
    logger.info("="*60)
    
    # Run all tests
    await analyze_montgomery_sites()
    await test_alternative_approach()
    
    logger.info("\n" + "="*60)
    logger.info("Investigation complete. Check the following files:")
    logger.info("  - montgomery_investigation.log (detailed logs)")
    logger.info("  - montgomery_response.html (HTTP response)")
    logger.info("  - montgomery_playwright.html (Playwright response)")
    logger.info("  - montgomery_screenshot.png (browser screenshot)")
    logger.info("  - montgomery_curl.html (curl response)")
    logger.info("  - montgomery_investigation_results.json (summary)")

if __name__ == "__main__":
    asyncio.run(main())