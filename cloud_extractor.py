"""
Cloud-compatible tax extractor using only HTTP requests.
No browser automation needed - works perfectly on Railway/cloud deployments.
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import logging
from typing import Dict, Optional, Any
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

class CloudTaxExtractor:
    """
    Cloud-friendly tax extractor that works with simple HTTP requests.
    Focused on jurisdictions that don't require JavaScript.
    """
    
    # These jurisdictions work well with simple HTTP requests
    SUPPORTED_JURISDICTIONS = {
        "Montgomery": {
            "name": "Montgomery County, TX",
            "method": "direct_url",
            "confidence": "high"
        },
        "Fort Bend": {
            "name": "Fort Bend County, TX", 
            "method": "direct_url",
            "confidence": "high"
        },
        "Chambers": {
            "name": "Chambers County, TX",
            "method": "direct_url",
            "confidence": "medium"
        },
        "Galveston": {
            "name": "Galveston County, TX",
            "method": "direct_url",
            "confidence": "medium"
        },
        "Aldine ISD": {
            "name": "Aldine ISD, TX",
            "method": "direct_link",
            "confidence": "high"
        },
        "Goose Creek ISD": {
            "name": "Goose Creek ISD, TX",
            "method": "direct_link",
            "confidence": "high"
        },
        "Spring Creek": {
            "name": "Spring Creek U.D., TX",
            "method": "direct_link",
            "confidence": "medium"
        },
        "Barbers Hill ISD": {
            "name": "Barbers Hill ISD, TX",
            "method": "direct_link",
            "confidence": "medium"
        }
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.last_request_time = 0
        self.rate_limit_seconds = 1  # Be respectful
    
    def _rate_limit(self):
        """Enforce rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self.last_request_time = time.time()
    
    def extract(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main extraction method for cloud deployment.
        
        Args:
            property_data: Dict with jurisdiction, tax_bill_link, account_number, etc.
            
        Returns:
            Dict with extraction results
        """
        jurisdiction = property_data.get("jurisdiction", "")
        tax_bill_link = property_data.get("tax_bill_link", "")
        account_number = property_data.get("account_number")
        
        # Check if jurisdiction is supported
        supported = False
        for key in self.SUPPORTED_JURISDICTIONS:
            if key.lower() in jurisdiction.lower():
                supported = True
                break
        
        if not supported:
            return {
                "success": False,
                "error": f"Jurisdiction '{jurisdiction}' not supported for cloud extraction",
                "supported_jurisdictions": list(self.SUPPORTED_JURISDICTIONS.keys())
            }
        
        # Rate limiting
        self._rate_limit()
        
        # Route to appropriate extractor
        if "montgomery" in jurisdiction.lower():
            return self._extract_montgomery(tax_bill_link, account_number)
        elif "fort bend" in jurisdiction.lower():
            return self._extract_fort_bend(tax_bill_link, account_number)
        elif "chambers" in jurisdiction.lower():
            return self._extract_chambers(tax_bill_link, account_number)
        elif "galveston" in jurisdiction.lower():
            return self._extract_galveston(tax_bill_link, account_number)
        elif any(isd in jurisdiction.lower() for isd in ["aldine", "goose creek", "spring creek", "barbers hill"]):
            return self._extract_isd(tax_bill_link, jurisdiction)
        else:
            return self._extract_generic(tax_bill_link, jurisdiction)
    
    def _extract_montgomery(self, url: str, account_number: Optional[str]) -> Dict[str, Any]:
        """Extract from Montgomery County - works great with HTTP"""
        try:
            # Extract account from URL if not provided
            if not account_number and "account=" in url:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                account_number = params.get("account", [None])[0]
            
            if not account_number or account_number == "montgomery":
                # Try to extract from the URL path or other parameters
                if "showdetail" in url:
                    # Sometimes the account is in other params
                    return {
                        "success": False,
                        "error": "Account number needed for Montgomery County"
                    }
            
            # Build direct URL
            base_url = "https://actweb.acttax.com/act_webdev/montgomery/showdetail2.jsp"
            full_url = f"{base_url}?account={account_number}"
            
            response = self.session.get(full_url, timeout=10)
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }
            
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            
            # Extract tax amount
            tax_amount = None
            amount_patterns = [
                r'Total Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Balance Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Amount Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Tax Due[:\s]+\$?([\d,]+\.?\d*)'
            ]
            
            for pattern in amount_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        tax_amount = float(match.group(1).replace(',', ''))
                        break
                    except:
                        pass
            
            # Extract address
            address = None
            addr_patterns = [
                r'Property Address[:\s]+([^\n]+)',
                r'Location[:\s]+([^\n]+)',
                r'Situs[:\s]+([^\n]+)'
            ]
            
            for pattern in addr_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    address = match.group(1).strip()
                    break
            
            return {
                "success": True,
                "tax_amount": tax_amount,
                "property_address": address,
                "account_number": account_number,
                "jurisdiction": "Montgomery County, TX",
                "extraction_method": "HTTP"
            }
            
        except Exception as e:
            logger.error(f"Montgomery extraction error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_fort_bend(self, url: str, account_number: Optional[str]) -> Dict[str, Any]:
        """Extract from Fort Bend County"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            
            # Fort Bend specific patterns
            tax_amount = None
            amount_match = re.search(r'Total Amount Due[:\s]+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
            if amount_match:
                try:
                    tax_amount = float(amount_match.group(1).replace(',', ''))
                except:
                    pass
            
            # Get address
            address = None
            addr_match = re.search(r'Property Location[:\s]+([^\n]+)', text, re.IGNORECASE)
            if addr_match:
                address = addr_match.group(1).strip()
            
            return {
                "success": True,
                "tax_amount": tax_amount,
                "property_address": address,
                "account_number": account_number,
                "jurisdiction": "Fort Bend County, TX",
                "extraction_method": "HTTP"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _extract_chambers(self, url: str, account_number: Optional[str]) -> Dict[str, Any]:
        """Extract from Chambers County"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for tax amounts in tables
            tax_amount = None
            tables = soup.find_all('table')
            for table in tables:
                text = table.get_text()
                if 'total' in text.lower() or 'due' in text.lower():
                    match = re.search(r'\$?([\d,]+\.?\d*)', text)
                    if match:
                        try:
                            amount = float(match.group(1).replace(',', ''))
                            if amount > 0 and amount < 1000000:  # Sanity check
                                tax_amount = amount
                                break
                        except:
                            pass
            
            return {
                "success": True,
                "tax_amount": tax_amount,
                "account_number": account_number,
                "jurisdiction": "Chambers County, TX",
                "extraction_method": "HTTP"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _extract_galveston(self, url: str, account_number: Optional[str]) -> Dict[str, Any]:
        """Extract from Galveston County"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            
            # Galveston patterns
            tax_amount = None
            patterns = [
                r'Total Tax Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Amount Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Balance[:\s]+\$?([\d,]+\.?\d*)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        tax_amount = float(match.group(1).replace(',', ''))
                        break
                    except:
                        pass
            
            return {
                "success": True,
                "tax_amount": tax_amount,
                "account_number": account_number,
                "jurisdiction": "Galveston County, TX",
                "extraction_method": "HTTP"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _extract_isd(self, url: str, jurisdiction: str) -> Dict[str, Any]:
        """Extract from ISD websites (usually simpler)"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            
            # ISD sites often have simple formats
            tax_amount = None
            patterns = [
                r'Total Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Tax Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Amount Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Balance[:\s]+\$?([\d,]+\.?\d*)',
                r'\$\s*([\d,]+\.?\d*)\s*(?:due|total|balance)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        amount = float(match.group(1).replace(',', ''))
                        if amount > 0 and amount < 100000:  # Sanity check for ISD
                            tax_amount = amount
                            break
                    except:
                        pass
            
            return {
                "success": True if tax_amount else False,
                "tax_amount": tax_amount,
                "jurisdiction": jurisdiction,
                "extraction_method": "HTTP",
                "error": None if tax_amount else "Could not find tax amount"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _extract_generic(self, url: str, jurisdiction: str) -> Dict[str, Any]:
        """Generic extraction for other jurisdictions"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            
            # Try common patterns
            tax_amount = None
            patterns = [
                r'(?:Total|Tax|Amount|Balance)\s*(?:Due|Owed|Payable)[:\s]+\$?([\d,]+\.?\d*)',
                r'\$\s*([\d,]+\.?\d*)\s*(?:due|total|balance|owed)',
                r'Pay\s*(?:This\s*)?Amount[:\s]+\$?([\d,]+\.?\d*)'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    # Take the largest reasonable amount found
                    amounts = []
                    for match in matches:
                        try:
                            amount = float(match.replace(',', ''))
                            if 10 < amount < 100000:  # Reasonable tax range
                                amounts.append(amount)
                        except:
                            pass
                    if amounts:
                        tax_amount = max(amounts)
                        break
            
            return {
                "success": True if tax_amount else False,
                "tax_amount": tax_amount,
                "jurisdiction": jurisdiction,
                "extraction_method": "HTTP-Generic",
                "confidence": "low" if tax_amount else None,
                "error": None if tax_amount else "Could not extract tax amount"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_supported_jurisdictions(self):
        """Get list of supported jurisdictions with confidence levels"""
        return self.SUPPORTED_JURISDICTIONS

# Singleton instance
cloud_extractor = CloudTaxExtractor()

def extract_tax_cloud(property_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for cloud extraction.
    
    Args:
        property_data: Dict containing jurisdiction, tax_bill_link, account_number, etc.
        
    Returns:
        Extraction results
    """
    return cloud_extractor.extract(property_data)