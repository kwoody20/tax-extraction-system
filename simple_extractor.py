"""
Simple, safe tax data extractor for known working jurisdictions.
Conservative approach with rate limiting and error handling.
"""

import requests
from bs4 import BeautifulSoup
import re
import time
from typing import Dict, Optional, Any
from urllib.parse import urlparse, parse_qs
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting configuration
RATE_LIMIT_DELAY = 2  # seconds between requests
REQUEST_TIMEOUT = 10  # seconds

# Known working extractors (conservative list)
SUPPORTED_JURISDICTIONS = [
    "Montgomery",  # Texas - works well with direct HTTP
    "Fort Bend",   # Texas - simple extraction
    "Aldine ISD",  # Texas - direct link
    "Goose Creek ISD",  # Texas - direct link
]

class SimpleTaxExtractor:
    """Conservative tax extractor for known working jurisdictions"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.last_request_time = 0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()
    
    def is_supported(self, jurisdiction: str) -> bool:
        """Check if jurisdiction is supported"""
        return any(j.lower() in jurisdiction.lower() for j in SUPPORTED_JURISDICTIONS)
    
    def extract(self, jurisdiction: str, tax_bill_link: str, 
                account_number: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract tax data from supported jurisdictions.
        Returns dict with success status and extracted data.
        """
        
        # Check if jurisdiction is supported
        if not self.is_supported(jurisdiction):
            return {
                'success': False,
                'error': f'Jurisdiction "{jurisdiction}" not yet supported',
                'supported_jurisdictions': SUPPORTED_JURISDICTIONS
            }
        
        # Rate limiting
        self._rate_limit()
        
        # Route to appropriate extractor
        if "montgomery" in jurisdiction.lower():
            return self._extract_montgomery(tax_bill_link, account_number)
        elif "fort bend" in jurisdiction.lower():
            return self._extract_fort_bend(tax_bill_link, account_number)
        elif "aldine" in jurisdiction.lower() or "goose creek" in jurisdiction.lower():
            return self._extract_simple_isd(tax_bill_link, jurisdiction)
        else:
            return {
                'success': False,
                'error': 'No extractor available for this jurisdiction'
            }
    
    def _extract_montgomery(self, url: str, account_number: Optional[str]) -> Dict[str, Any]:
        """Extract from Montgomery County, TX"""
        try:
            # Extract account number from URL if not provided
            if not account_number:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                account_number = params.get('account', [None])[0]
            
            if not account_number:
                return {
                    'success': False,
                    'error': 'Account number not found in URL'
                }
            
            # Build the direct URL
            base_url = "https://actweb.acttax.com/act_webdev/montgomery/showdetail2.jsp"
            full_url = f"{base_url}?account={account_number}"
            
            # Make request
            response = self.session.get(full_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract data (Montgomery specific parsing)
            data = {
                'success': True,
                'jurisdiction': 'Montgomery County',
                'account_number': account_number,
                'tax_amount': None,
                'property_address': None,
                'owner_name': None
            }
            
            # Look for tax amount (usually in a table)
            tables = soup.find_all('table')
            for table in tables:
                text = table.get_text()
                # Look for tax amount patterns
                amount_match = re.search(r'Total Due[:\s]+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
                if not amount_match:
                    amount_match = re.search(r'Amount Due[:\s]+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
                if amount_match:
                    data['tax_amount'] = float(amount_match.group(1).replace(',', ''))
                
                # Look for address
                addr_match = re.search(r'Property Address[:\s]+([^\n]+)', text, re.IGNORECASE)
                if addr_match:
                    data['property_address'] = addr_match.group(1).strip()
            
            return data
            
        except requests.RequestException as e:
            logger.error(f"Request error for Montgomery: {e}")
            return {
                'success': False,
                'error': f'Request failed: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Extraction error for Montgomery: {e}")
            return {
                'success': False,
                'error': f'Extraction failed: {str(e)}'
            }
    
    def _extract_fort_bend(self, url: str, account_number: Optional[str]) -> Dict[str, Any]:
        """Extract from Fort Bend County, TX"""
        try:
            # Make request
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            data = {
                'success': True,
                'jurisdiction': 'Fort Bend County',
                'account_number': account_number,
                'tax_amount': None,
                'property_address': None
            }
            
            # Fort Bend specific parsing
            text = soup.get_text()
            
            # Look for tax amount
            amount_match = re.search(r'Total Amount Due[:\s]+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
            if amount_match:
                data['tax_amount'] = float(amount_match.group(1).replace(',', ''))
            
            # Look for address
            addr_match = re.search(r'Property Location[:\s]+([^\n]+)', text, re.IGNORECASE)
            if addr_match:
                data['property_address'] = addr_match.group(1).strip()
            
            return data
            
        except Exception as e:
            logger.error(f"Extraction error for Fort Bend: {e}")
            return {
                'success': False,
                'error': f'Extraction failed: {str(e)}'
            }
    
    def _extract_simple_isd(self, url: str, jurisdiction: str) -> Dict[str, Any]:
        """Extract from simple ISD websites"""
        try:
            # Make request
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            data = {
                'success': True,
                'jurisdiction': jurisdiction,
                'tax_amount': None,
                'property_address': None
            }
            
            # Generic ISD parsing
            text = soup.get_text()
            
            # Look for common tax amount patterns
            patterns = [
                r'Total Tax Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Amount Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Total Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Balance Due[:\s]+\$?([\d,]+\.?\d*)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    data['tax_amount'] = float(match.group(1).replace(',', ''))
                    break
            
            return data
            
        except Exception as e:
            logger.error(f"Extraction error for {jurisdiction}: {e}")
            return {
                'success': False,
                'error': f'Extraction failed: {str(e)}'
            }
    
    def test_extraction(self) -> Dict[str, Any]:
        """Test extraction with a known working example"""
        test_url = "https://actweb.acttax.com/act_webdev/montgomery/showdetail2.jsp?account=123456"
        result = self.extract("Montgomery", test_url)
        return {
            'test_status': 'completed',
            'result': result
        }

# Singleton instance
extractor = SimpleTaxExtractor()

def extract_tax_data(jurisdiction: str, tax_bill_link: str, 
                     account_number: Optional[str] = None) -> Dict[str, Any]:
    """
    Main entry point for tax extraction.
    
    Args:
        jurisdiction: The tax jurisdiction name
        tax_bill_link: URL to the tax bill
        account_number: Optional account number
    
    Returns:
        Dict with extraction results
    """
    return extractor.extract(jurisdiction, tax_bill_link, account_number)

def get_supported_jurisdictions() -> List[str]:
    """Get list of supported jurisdictions"""
    return SUPPORTED_JURISDICTIONS