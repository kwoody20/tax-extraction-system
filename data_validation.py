#!/usr/bin/env python3
"""
Data validation and sanitization for tax extraction
"""

import re
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

class DataValidator:
    """Validates and sanitizes extracted tax data"""
    
    # Regex patterns for validation
    PATTERNS = {
        'account_number': r'^[A-Z0-9\-]+$',
        'parcel_number': r'^[A-Z0-9\-\.]+$',
        'zip_code': r'^\d{5}(-\d{4})?$',
        'phone': r'^[\d\-\(\)\s\+]+$',
        'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'currency': r'^\$?[\d,]+\.?\d{0,2}$',
        'date': r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$',
    }
    
    # Valid US state codes
    US_STATES = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
        'DC', 'PR', 'VI', 'GU', 'AS', 'MP'
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.validation_errors: List[Dict[str, Any]] = []
        self.validation_warnings: List[Dict[str, Any]] = []
    
    def validate_currency(self, 
                         value: Any, 
                         min_amount: float = 0.0,
                         max_amount: float = 1000000.0) -> Optional[float]:
        """
        Validate and parse currency values
        
        Args:
            value: Value to validate (string or number)
            min_amount: Minimum valid amount
            max_amount: Maximum valid amount
        
        Returns:
            Float value or None if invalid
        """
        if value is None or value == '':
            return None
        
        try:
            # Convert to string and clean
            str_value = str(value)
            
            # Remove currency symbols and whitespace
            cleaned = str_value.replace('$', '').replace(',', '').strip()
            
            # Handle negative values
            is_negative = False
            if cleaned.startswith('(') and cleaned.endswith(')'):
                cleaned = cleaned[1:-1]
                is_negative = True
            elif cleaned.startswith('-'):
                cleaned = cleaned[1:]
                is_negative = True
            
            # Parse to decimal for precision
            decimal_value = Decimal(cleaned)
            
            # Apply negative if needed
            if is_negative:
                decimal_value = -decimal_value
            
            # Convert to float
            float_value = float(decimal_value)
            
            # Validate range
            if float_value < min_amount:
                self.validation_warnings.append({
                    'field': 'currency',
                    'value': value,
                    'warning': f'Amount {float_value} is below minimum {min_amount}'
                })
            
            if float_value > max_amount:
                self.validation_warnings.append({
                    'field': 'currency',
                    'value': value,
                    'warning': f'Amount {float_value} exceeds maximum {max_amount}'
                })
            
            return float_value
            
        except (InvalidOperation, ValueError) as e:
            self.validation_errors.append({
                'field': 'currency',
                'value': value,
                'error': str(e)
            })
            return None
    
    def validate_address(self, address: str) -> Optional[Dict[str, str]]:
        """
        Validate and parse address into components
        
        Args:
            address: Address string to validate
        
        Returns:
            Dictionary with address components or None if invalid
        """
        if not address or not isinstance(address, str):
            return None
        
        # Clean the address
        cleaned = ' '.join(address.split())  # Normalize whitespace
        
        # Basic address parsing (simplified)
        # Pattern: number street_name street_type, city, state zip
        pattern = r'^(\d+)\s+(.+?),\s*([^,]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)$'
        
        match = re.match(pattern, cleaned, re.IGNORECASE)
        if match:
            return {
                'street_number': match.group(1),
                'street_name': match.group(2),
                'city': match.group(3),
                'state': match.group(4).upper(),
                'zip_code': match.group(5),
                'full_address': cleaned
            }
        
        # Try alternative patterns
        # Pattern without street number
        pattern2 = r'^(.+?),\s*([^,]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)$'
        match = re.match(pattern2, cleaned, re.IGNORECASE)
        if match:
            return {
                'street_name': match.group(1),
                'city': match.group(2),
                'state': match.group(3).upper(),
                'zip_code': match.group(4),
                'full_address': cleaned
            }
        
        # If no pattern matches, return cleaned address
        return {'full_address': cleaned}
    
    def validate_date(self, date_str: str) -> Optional[date]:
        """
        Validate and parse date strings
        
        Args:
            date_str: Date string to parse
        
        Returns:
            date object or None if invalid
        """
        if not date_str or not isinstance(date_str, str):
            return None
        
        # Common date formats
        date_formats = [
            '%m/%d/%Y',
            '%m-%d-%Y',
            '%Y-%m-%d',
            '%m/%d/%y',
            '%m-%d-%y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y'
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str.strip(), fmt).date()
                
                # Validate year is reasonable
                current_year = datetime.now().year
                if parsed_date.year < 1900 or parsed_date.year > current_year + 10:
                    self.validation_warnings.append({
                        'field': 'date',
                        'value': date_str,
                        'warning': f'Year {parsed_date.year} seems unusual'
                    })
                
                return parsed_date
                
            except ValueError:
                continue
        
        self.validation_errors.append({
            'field': 'date',
            'value': date_str,
            'error': 'Could not parse date'
        })
        return None
    
    def validate_account_number(self, account_num: str) -> Optional[str]:
        """
        Validate and clean account numbers
        
        Args:
            account_num: Account number to validate
        
        Returns:
            Cleaned account number or None if invalid
        """
        if not account_num:
            return None
        
        # Convert to string and clean
        cleaned = str(account_num).strip().upper()
        
        # Remove common separators but keep hyphens
        cleaned = cleaned.replace(' ', '').replace('.', '')
        
        # Check if it matches expected pattern
        if re.match(self.PATTERNS['account_number'], cleaned):
            return cleaned
        
        # If it contains only alphanumeric and common separators, accept it
        if re.match(r'^[A-Z0-9\-\.\/]+$', cleaned):
            return cleaned
        
        self.validation_warnings.append({
            'field': 'account_number',
            'value': account_num,
            'warning': 'Account number contains unexpected characters'
        })
        
        return cleaned
    
    def validate_state(self, state_code: str) -> Optional[str]:
        """
        Validate US state code
        
        Args:
            state_code: State code to validate
        
        Returns:
            Validated state code or None
        """
        if not state_code:
            return None
        
        cleaned = state_code.strip().upper()
        
        if cleaned in self.US_STATES:
            return cleaned
        
        # Check for common full state names
        state_mappings = {
            'TEXAS': 'TX',
            'CALIFORNIA': 'CA',
            'NEW YORK': 'NY',
            'FLORIDA': 'FL',
            'ARIZONA': 'AZ',
            'LOUISIANA': 'LA',
            'OKLAHOMA': 'OK',
        }
        
        if cleaned in state_mappings:
            return state_mappings[cleaned]
        
        self.validation_errors.append({
            'field': 'state',
            'value': state_code,
            'error': 'Invalid state code'
        })
        
        return None
    
    def validate_property_data(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validate complete property tax data
        
        Args:
            data: Property data dictionary
        
        Returns:
            Tuple of (validated_data, list of issues)
        """
        validated = {}
        issues = []
        
        # Validate and clean each field
        field_validators = {
            'account_number': self.validate_account_number,
            'property_address': self.validate_address,
            'amount_due': lambda x: self.validate_currency(x, 0, 1000000),
            'previous_year_taxes': lambda x: self.validate_currency(x, 0, 1000000),
            'next_due_date': self.validate_date,
            'state': self.validate_state,
        }
        
        for field, validator in field_validators.items():
            if field in data and data[field] is not None:
                validated_value = validator(data[field])
                if validated_value is not None:
                    validated[field] = validated_value
                else:
                    issues.append(f"Invalid {field}: {data[field]}")
        
        # Copy over fields that don't need validation
        copy_fields = ['property_id', 'property_name', 'jurisdiction', 
                      'extraction_status', 'extraction_timestamp', 'extraction_notes']
        
        for field in copy_fields:
            if field in data:
                validated[field] = data[field]
        
        # Add validation metadata
        validated['validation_timestamp'] = datetime.now().isoformat()
        validated['validation_issues'] = issues
        
        return validated, issues
    
    def sanitize_html(self, html_str: str) -> str:
        """
        Remove HTML tags and clean text
        
        Args:
            html_str: HTML string to clean
        
        Returns:
            Cleaned text
        """
        if not html_str:
            return ''
        
        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', html_str)
        
        # Decode HTML entities
        import html
        clean_text = html.unescape(clean_text)
        
        # Normalize whitespace
        clean_text = ' '.join(clean_text.split())
        
        return clean_text.strip()
    
    def get_validation_report(self) -> Dict[str, Any]:
        """Get validation summary report"""
        return {
            'total_errors': len(self.validation_errors),
            'total_warnings': len(self.validation_warnings),
            'errors': self.validation_errors[-10:],  # Last 10 errors
            'warnings': self.validation_warnings[-10:],  # Last 10 warnings
            'timestamp': datetime.now().isoformat()
        }

class DataNormalizer:
    """Normalize data formats for consistency"""
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone number to standard format"""
        if not phone:
            return ''
        
        # Remove all non-digits
        digits = re.sub(r'\D', '', phone)
        
        # Format as (XXX) XXX-XXXX if 10 digits
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        
        # Format as +X (XXX) XXX-XXXX if 11 digits starting with 1
        if len(digits) == 11 and digits[0] == '1':
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        
        return phone  # Return original if can't normalize
    
    @staticmethod
    def normalize_case(text: str, style: str = 'title') -> str:
        """Normalize text case"""
        if not text:
            return ''
        
        if style == 'upper':
            return text.upper()
        elif style == 'lower':
            return text.lower()
        elif style == 'title':
            # Proper title case for addresses
            words = text.split()
            excluded = {'of', 'and', 'the', 'in', 'at', 'by', 'for', 'to'}
            result = []
            
            for i, word in enumerate(words):
                if i == 0 or word.lower() not in excluded:
                    result.append(word.capitalize())
                else:
                    result.append(word.lower())
            
            return ' '.join(result)
        
        return text
    
    @staticmethod
    def normalize_zip(zip_code: str) -> str:
        """Normalize ZIP code format"""
        if not zip_code:
            return ''
        
        # Remove all non-digits and hyphens
        cleaned = re.sub(r'[^\d\-]', '', zip_code)
        
        # Match 5 digit or 5+4 format
        if re.match(r'^\d{5}$', cleaned):
            return cleaned
        elif re.match(r'^\d{5}\d{4}$', cleaned):
            return f"{cleaned[:5]}-{cleaned[5:]}"
        elif re.match(r'^\d{5}-\d{4}$', cleaned):
            return cleaned
        
        return zip_code  # Return original if can't normalize