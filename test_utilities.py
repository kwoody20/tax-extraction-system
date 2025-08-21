#!/usr/bin/env python3
"""
Testing utilities for tax extraction system
"""

import unittest
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
import tempfile
import logging
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch, MagicMock

# Import modules to test
from config import ConfigManager, ScraperConfig, SystemConfig
from error_handling import (
    ErrorHandler, retry_with_backoff, CircuitBreaker,
    NetworkError, ParseError, ValidationError
)
from data_validation import DataValidator, DataNormalizer

logger = logging.getLogger(__name__)

class TestDataGenerator:
    """Generate test data for tax extraction testing"""
    
    @staticmethod
    def create_test_excel(num_properties: int = 10) -> str:
        """Create test Excel file with sample property data"""
        data = []
        
        domains = [
            'actweb.acttax.com',
            'www.hctax.net',
            'treasurer.maricopa.gov',
            'tax.aldine.k12.tx.us'
        ]
        
        for i in range(num_properties):
            domain = domains[i % len(domains)]
            data.append({
                'Property ID': f'PROP-{i:04d}',
                'Property Name': f'Test Property {i}',
                'Property Address': f'{100 + i} Main St, City, TX 75001',
                'Jurisdiction': f'County {i % 3}',
                'State': 'TX',
                'Acct Number': f'ACC-{i:06d}',
                'Tax Bill Link': f'https://{domain}/property?id={i}'
            })
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        df = pd.DataFrame(data)
        df.to_excel(temp_file.name, index=False)
        
        return temp_file.name
    
    @staticmethod
    def create_test_config() -> Dict[str, Any]:
        """Create test configuration"""
        return {
            'system': {
                'headless': True,
                'max_workers': 2,
                'batch_size': 5,
                'log_level': 'DEBUG',
                'output_dir': 'test_output',
                'save_screenshots': False,
                'save_html': False
            },
            'scrapers': {
                'test.domain.com': {
                    'name': 'Test County',
                    'search_method': 'direct_link',
                    'selectors': {
                        'property_address': '//div[@class="address"]',
                        'amount_due': '//span[@class="amount"]'
                    },
                    'requires_javascript': False,
                    'rate_limit_delay': 0.5
                }
            }
        }
    
    @staticmethod
    def create_mock_response(status_code: int = 200, 
                           content: str = '<html><body>Test</body></html>') -> Mock:
        """Create mock HTTP response"""
        response = Mock()
        response.status_code = status_code
        response.text = content
        response.content = content.encode('utf-8')
        response.raise_for_status = Mock()
        if status_code >= 400:
            response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        return response

class TestConfiguration(unittest.TestCase):
    """Test configuration management"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / 'test_config.json'
    
    def test_load_default_config(self):
        """Test loading default configuration"""
        config = ConfigManager(str(self.config_file))
        
        self.assertIsNotNone(config.system_config)
        self.assertIsInstance(config.system_config, SystemConfig)
        self.assertTrue(config.system_config.headless)
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration"""
        config = ConfigManager(str(self.config_file))
        
        # Modify configuration
        config.system_config.max_workers = 5
        config.add_scraper_config('test.com', {'name': 'Test', 'search_method': 'direct_link'})
        
        # Save configuration
        config.save_config()
        self.assertTrue(self.config_file.exists())
        
        # Load configuration
        new_config = ConfigManager(str(self.config_file))
        self.assertEqual(new_config.system_config.max_workers, 5)
        self.assertIn('test.com', new_config.scraper_configs)
    
    def test_validate_config(self):
        """Test configuration validation"""
        config = ConfigManager(str(self.config_file))
        
        # Valid configuration
        self.assertTrue(config.validate_config())
        
        # Invalid configuration
        config.system_config.max_workers = -1
        self.assertFalse(config.validate_config())
        
        config.system_config.max_workers = 1
        config.system_config.min_valid_amount = 100
        config.system_config.max_valid_amount = 50
        self.assertFalse(config.validate_config())

class TestErrorHandling(unittest.TestCase):
    """Test error handling and retry logic"""
    
    def test_error_handler_logging(self):
        """Test error logging"""
        handler = ErrorHandler()
        
        error = NetworkError("Test error")
        context = {'url': 'https://test.com', 'attempt': 1}
        
        record = handler.log_error(error, context)
        
        self.assertEqual(record['error_type'], 'NetworkError')
        self.assertEqual(record['error_message'], 'Test error')
        self.assertEqual(record['context'], context)
        self.assertEqual(len(handler.error_history), 1)
    
    def test_should_retry_logic(self):
        """Test retry decision logic"""
        handler = ErrorHandler()
        
        # Should retry network errors
        self.assertTrue(handler.should_retry(NetworkError("test"), 1, 3))
        
        # Should not retry authentication errors
        self.assertFalse(handler.should_retry(AuthenticationError("test"), 1, 3))
        
        # Should not exceed max attempts
        self.assertFalse(handler.should_retry(NetworkError("test"), 3, 3))
    
    def test_retry_decorator(self):
        """Test retry decorator"""
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, base_delay=0.1)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Network error")
            return "success"
        
        result = flaky_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
    
    def test_circuit_breaker(self):
        """Test circuit breaker pattern"""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        def failing_function():
            raise Exception("Failure")
        
        # First failure
        with self.assertRaises(Exception):
            breaker.call(failing_function)
        
        # Second failure - should open circuit
        with self.assertRaises(Exception):
            breaker.call(failing_function)
        
        # Circuit should be open
        self.assertEqual(breaker.state, 'open')
        
        # Should not execute function when open
        with self.assertRaises(Exception) as context:
            breaker.call(failing_function)
        self.assertIn("Circuit breaker is open", str(context.exception))

class TestDataValidation(unittest.TestCase):
    """Test data validation and sanitization"""
    
    def setUp(self):
        self.validator = DataValidator()
    
    def test_validate_currency(self):
        """Test currency validation"""
        # Valid currencies
        self.assertEqual(self.validator.validate_currency("$1,234.56"), 1234.56)
        self.assertEqual(self.validator.validate_currency("1234.56"), 1234.56)
        self.assertEqual(self.validator.validate_currency("$1,234"), 1234.0)
        
        # Invalid currencies
        self.assertIsNone(self.validator.validate_currency("invalid"))
        self.assertIsNone(self.validator.validate_currency(""))
        self.assertIsNone(self.validator.validate_currency(None))
    
    def test_validate_address(self):
        """Test address validation"""
        # Valid address
        result = self.validator.validate_address("123 Main St, Austin, TX 78701")
        self.assertIsNotNone(result)
        self.assertEqual(result['city'], 'Austin')
        self.assertEqual(result['state'], 'TX')
        self.assertEqual(result['zip_code'], '78701')
        
        # Address without street number
        result = self.validator.validate_address("Main Street, Houston, TX 77001")
        self.assertIsNotNone(result)
        self.assertEqual(result['city'], 'Houston')
        
        # Invalid address
        result = self.validator.validate_address("Invalid")
        self.assertEqual(result, {'full_address': 'Invalid'})
    
    def test_validate_date(self):
        """Test date validation"""
        # Valid dates
        self.assertIsNotNone(self.validator.validate_date("12/31/2024"))
        self.assertIsNotNone(self.validator.validate_date("2024-12-31"))
        self.assertIsNotNone(self.validator.validate_date("December 31, 2024"))
        
        # Invalid dates
        self.assertIsNone(self.validator.validate_date("invalid"))
        self.assertIsNone(self.validator.validate_date("13/32/2024"))
    
    def test_validate_account_number(self):
        """Test account number validation"""
        # Valid account numbers
        self.assertEqual(self.validator.validate_account_number("ACC-123456"), "ACC-123456")
        self.assertEqual(self.validator.validate_account_number("acc-123456"), "ACC-123456")
        self.assertEqual(self.validator.validate_account_number("123456"), "123456")
        
        # Account with spaces
        self.assertEqual(self.validator.validate_account_number("ACC 123 456"), "ACC123456")
    
    def test_validate_state(self):
        """Test state code validation"""
        # Valid state codes
        self.assertEqual(self.validator.validate_state("TX"), "TX")
        self.assertEqual(self.validator.validate_state("tx"), "TX")
        self.assertEqual(self.validator.validate_state("TEXAS"), "TX")
        
        # Invalid state codes
        self.assertIsNone(self.validator.validate_state("XX"))
        self.assertIsNone(self.validator.validate_state("Invalid"))
    
    def test_sanitize_html(self):
        """Test HTML sanitization"""
        html = '<div>Property <b>Address</b>: 123 Main St</div>'
        clean = self.validator.sanitize_html(html)
        self.assertEqual(clean, 'Property Address: 123 Main St')
        
        # HTML entities
        html = '&lt;Property&gt; &amp; Address'
        clean = self.validator.sanitize_html(html)
        self.assertEqual(clean, '<Property> & Address')

class TestDataNormalizer(unittest.TestCase):
    """Test data normalization"""
    
    def test_normalize_phone(self):
        """Test phone number normalization"""
        normalizer = DataNormalizer()
        
        self.assertEqual(normalizer.normalize_phone("5551234567"), "(555) 123-4567")
        self.assertEqual(normalizer.normalize_phone("15551234567"), "+1 (555) 123-4567")
        self.assertEqual(normalizer.normalize_phone("555-123-4567"), "(555) 123-4567")
    
    def test_normalize_case(self):
        """Test text case normalization"""
        normalizer = DataNormalizer()
        
        self.assertEqual(normalizer.normalize_case("HELLO WORLD", "title"), "Hello World")
        self.assertEqual(normalizer.normalize_case("hello world", "upper"), "HELLO WORLD")
        self.assertEqual(normalizer.normalize_case("Hello World", "lower"), "hello world")
        
        # Title case with excluded words
        self.assertEqual(
            normalizer.normalize_case("the house of the rising sun", "title"),
            "The House of the Rising Sun"
        )
    
    def test_normalize_zip(self):
        """Test ZIP code normalization"""
        normalizer = DataNormalizer()
        
        self.assertEqual(normalizer.normalize_zip("12345"), "12345")
        self.assertEqual(normalizer.normalize_zip("123456789"), "12345-6789")
        self.assertEqual(normalizer.normalize_zip("12345-6789"), "12345-6789")
        self.assertEqual(normalizer.normalize_zip("12345 6789"), "12345-6789")

class IntegrationTest(unittest.TestCase):
    """Integration tests for the complete system"""
    
    def setUp(self):
        self.test_data_file = TestDataGenerator.create_test_excel()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        # Clean up test files
        Path(self.test_data_file).unlink(missing_ok=True)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('requests.Session.get')
    def test_end_to_end_extraction(self, mock_get):
        """Test end-to-end extraction process"""
        from robust_tax_extractor import RobustTaxExtractor
        
        # Mock HTTP responses
        mock_get.return_value = TestDataGenerator.create_mock_response(
            200,
            '''
            <html>
            <body>
                <td>Property Address</td><td>123 Test St, Austin, TX 78701</td>
                <td>Total Due</td><td>$1,234.56</td>
                <td>Prior Year</td><td>$1,100.00</td>
            </body>
            </html>
            '''
        )
        
        # Create extractor with test data
        with patch('robust_tax_extractor.get_config') as mock_config:
            config = ConfigManager()
            config.system_config.output_dir = self.temp_dir
            config.system_config.save_intermediate = False
            mock_config.return_value = config
            
            extractor = RobustTaxExtractor(self.test_data_file)
            
            # Process first batch
            results = extractor.process_batch(0, 5)
            
            self.assertEqual(len(results), 5)
            
            # Check extraction results
            for result in results:
                self.assertIn(result.extraction_status, 
                            ['success', 'unsupported_domain', 'no_data'])
    
    def test_validation_integration(self):
        """Test validation integration"""
        validator = DataValidator()
        
        test_data = {
            'property_id': 'PROP-001',
            'property_name': 'Test Property',
            'property_address': '123 Main St, Austin, TX 78701',
            'account_number': 'ACC-123456',
            'amount_due': '$1,234.56',
            'previous_year_taxes': '1100.00',
            'next_due_date': '12/31/2024',
            'state': 'TX'
        }
        
        validated, issues = validator.validate_property_data(test_data)
        
        self.assertEqual(len(issues), 0)
        self.assertEqual(validated['amount_due'], 1234.56)
        self.assertEqual(validated['previous_year_taxes'], 1100.00)
        self.assertIsNotNone(validated['next_due_date'])

def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestDataValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestDataNormalizer))
    suite.addTests(loader.loadTestsFromTestCase(IntegrationTest))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)