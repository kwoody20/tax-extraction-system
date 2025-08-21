#!/usr/bin/env python3
"""
Robust Property Tax Information Extractor
Enhanced version with error handling, retry logic, and data validation
"""

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from urllib.parse import urlparse, parse_qs
import logging
import json
import re
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib

# Import our custom modules
from config import get_config, ScraperConfig
from error_handling import (
    retry_with_backoff, ErrorHandler, CircuitBreaker,
    NetworkError, ParseError, ValidationError, RateLimitError,
    safe_extract, validate_response
)
from data_validation import DataValidator, DataNormalizer

# Configure logging with enhanced format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('robust_tax_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ExtractionResult:
    """Enhanced extraction result with validation and metadata"""
    property_id: str
    property_name: str
    extraction_status: str
    extraction_timestamp: str
    
    # Tax information
    property_address: Optional[str] = None
    account_number: Optional[str] = None
    tax_id: Optional[str] = None
    amount_due: Optional[float] = None
    previous_year_taxes: Optional[float] = None
    next_due_date: Optional[str] = None
    
    # Metadata
    extraction_method: Optional[str] = None
    extraction_duration: Optional[float] = None
    retry_count: int = 0
    validation_status: Optional[str] = None
    validation_issues: List[str] = None
    error_details: Optional[str] = None
    
    # Source information
    source_url: Optional[str] = None
    source_domain: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary with None values handled"""
        data = asdict(self)
        # Ensure lists are initialized
        if data['validation_issues'] is None:
            data['validation_issues'] = []
        return data

class RobustTaxExtractor:
    """Enhanced tax extractor with robust error handling and validation"""
    
    def __init__(self, excel_file: str, config_file: Optional[str] = None):
        self.excel_file = excel_file
        self.df = self._load_excel_safely(excel_file)
        self.config = get_config()
        self.error_handler = ErrorHandler()
        self.validator = DataValidator()
        self.normalizer = DataNormalizer()
        self.results: List[ExtractionResult] = []
        self.session = self._create_session()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Create output directory
        self.output_dir = Path(self.config.system_config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for avoiding duplicate requests
        self.request_cache: Dict[str, Any] = {}
        
        logger.info(f"Initialized RobustTaxExtractor with {len(self.df)} properties")
    
    def _load_excel_safely(self, file_path: str) -> pd.DataFrame:
        """Safely load Excel file with error handling"""
        try:
            df = pd.read_excel(file_path)
            logger.info(f"Successfully loaded {len(df)} records from {file_path}")
            
            # Validate required columns
            required_columns = ['Property ID', 'Property Name']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise ValidationError(f"Missing required columns: {missing_columns}")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to load Excel file: {e}")
            raise
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            'User-Agent': self.config.system_config.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        return session
    
    def _get_circuit_breaker(self, domain: str) -> CircuitBreaker:
        """Get or create circuit breaker for domain"""
        if domain not in self.circuit_breakers:
            self.circuit_breakers[domain] = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60,
                expected_exception=Exception
            )
        return self.circuit_breakers[domain]
    
    @retry_with_backoff(max_attempts=3, exceptions=(NetworkError, requests.RequestException))
    def _fetch_url(self, url: str, timeout: int = 30) -> requests.Response:
        """Fetch URL with retry logic and caching"""
        # Check cache
        cache_key = hashlib.md5(url.encode()).hexdigest()
        if cache_key in self.request_cache:
            logger.debug(f"Using cached response for {url}")
            return self.request_cache[cache_key]
        
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            
            # Cache successful responses
            self.request_cache[cache_key] = response
            
            return response
            
        except requests.Timeout:
            raise NetworkError(f"Timeout fetching {url}")
        except requests.RequestException as e:
            raise NetworkError(f"Error fetching {url}: {e}")
    
    def extract_property(self, row: pd.Series) -> ExtractionResult:
        """Extract tax information for a single property"""
        start_time = time.time()
        scraper_config = None  # Initialize to avoid UnboundLocalError
        
        # Initialize result
        result = ExtractionResult(
            property_id=str(row.get('Property ID', '')),
            property_name=str(row.get('Property Name', '')),
            extraction_status='pending',
            extraction_timestamp=datetime.now().isoformat(),
            source_url=row.get('Tax Bill Link'),
            validation_issues=[]
        )
        
        try:
            # Check if URL exists
            if pd.isna(row.get('Tax Bill Link')):
                result.extraction_status = 'no_url'
                result.error_details = 'No tax bill link provided'
                return result
            
            url = row['Tax Bill Link']
            domain = urlparse(url).netloc
            result.source_domain = domain
            
            # Get scraper configuration
            scraper_config = self.config.get_scraper_config(domain)
            if not scraper_config:
                result.extraction_status = 'unsupported_domain'
                result.error_details = f'No configuration for domain: {domain}'
                return result
            
            # Use circuit breaker
            circuit_breaker = self._get_circuit_breaker(domain)
            
            # Extract based on method
            if scraper_config.requires_javascript:
                extraction_data = circuit_breaker.call(
                    self._extract_with_selenium,
                    url, scraper_config, row
                )
            else:
                extraction_data = circuit_breaker.call(
                    self._extract_with_requests,
                    url, scraper_config, row
                )
            
            # Update result with extracted data
            if extraction_data:
                for key, value in extraction_data.items():
                    if hasattr(result, key):
                        setattr(result, key, value)
                
                # Validate extracted data
                validated_data, issues = self.validator.validate_property_data(extraction_data)
                result.validation_issues = issues
                result.validation_status = 'valid' if not issues else 'has_issues'
                
                # Update with validated data
                for key, value in validated_data.items():
                    if hasattr(result, key):
                        setattr(result, key, value)
                
                result.extraction_status = 'success'
            else:
                result.extraction_status = 'no_data'
                result.error_details = 'No data extracted'
            
        except Exception as e:
            logger.error(f"Error extracting property {result.property_id}: {e}")
            result.extraction_status = 'failed'
            result.error_details = str(e)
            
            # Log to error handler
            self.error_handler.log_error(
                e,
                {
                    'property_id': result.property_id,
                    'url': url if 'url' in locals() else None,
                    'domain': domain if 'domain' in locals() else None
                }
            )
        
        finally:
            # Record extraction duration
            result.extraction_duration = time.time() - start_time
            result.extraction_method = 'selenium' if scraper_config and scraper_config.requires_javascript else 'requests'
        
        return result
    
    def _extract_with_requests(self, 
                              url: str, 
                              config: ScraperConfig, 
                              row: pd.Series) -> Dict[str, Any]:
        """Extract data using requests library"""
        logger.debug(f"Extracting with requests: {url}")
        
        response = self._fetch_url(url, timeout=config.timeout)
        
        # Parse HTML
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        extracted_data = {}
        
        # Extract account number from URL if available
        parsed_url = urlparse(url)
        params = parse_qs(parsed_url.query)
        
        for param_name in ['can', 'account', 'acct', 'id']:
            if param_name in params:
                extracted_data['account_number'] = params[param_name][0]
                break
        
        # Use existing account number if not found in URL
        if 'account_number' not in extracted_data and row.get('Acct Number'):
            extracted_data['account_number'] = self.validator.validate_account_number(
                row.get('Acct Number')
            )
        
        # Try to extract common fields
        extraction_patterns = {
            'property_address': [
                ('td', {'text': re.compile('Property Address')}),
                ('span', {'class': 'property-address'}),
                ('div', {'class': 'address'}),
            ],
            'amount_due': [
                ('td', {'text': re.compile('Total Due|Amount Due|Balance')}),
                ('span', {'class': 'amount-due'}),
                ('div', {'class': 'total-amount'}),
            ],
            'previous_year_taxes': [
                ('td', {'text': re.compile('Prior Year|Previous Year|2023')}),
                ('span', {'class': 'prior-year'}),
            ],
        }
        
        for field, patterns in extraction_patterns.items():
            value = None
            for tag, attrs in patterns:
                elements = soup.find_all(tag, attrs)
                for element in elements:
                    # Try to find value in next sibling or parent
                    next_elem = element.find_next_sibling()
                    if next_elem:
                        value = next_elem.get_text(strip=True)
                        break
                
                if value:
                    break
            
            if value:
                # Clean and validate based on field type
                if field in ['amount_due', 'previous_year_taxes']:
                    value = self.validator.validate_currency(value)
                elif field == 'property_address':
                    value = self.validator.sanitize_html(value)
                
                extracted_data[field] = value
        
        return extracted_data
    
    def _extract_with_selenium(self, 
                              url: str, 
                              config: ScraperConfig, 
                              row: pd.Series) -> Dict[str, Any]:
        """Extract data using Selenium for JavaScript-heavy sites"""
        logger.debug(f"Extracting with Selenium: {url}")
        
        driver = None
        extracted_data = {}
        
        try:
            # Setup Chrome driver
            options = Options()
            if self.config.system_config.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            driver = webdriver.Chrome(options=options)
            wait = WebDriverWait(driver, config.wait_time)
            
            # Navigate to URL
            driver.get(url)
            
            # Wait for page to load
            time.sleep(2)
            
            # Extract using configured selectors
            for field, xpath in config.selectors.items():
                try:
                    element = wait.until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    value = element.text.strip()
                    
                    # Validate and clean based on field type
                    if 'amount' in field.lower() or 'tax' in field.lower():
                        value = self.validator.validate_currency(value)
                    elif 'address' in field.lower():
                        value = self.validator.sanitize_html(value)
                    elif 'date' in field.lower():
                        value = self.validator.validate_date(value)
                    
                    extracted_data[field] = value
                    
                except (TimeoutException, NoSuchElementException):
                    logger.debug(f"Could not find element for {field} with xpath: {xpath}")
            
            # Save screenshot if configured
            if self.config.system_config.save_screenshots:
                screenshot_path = self.output_dir / 'screenshots' / f"{row['Property ID']}.png"
                screenshot_path.parent.mkdir(exist_ok=True)
                driver.save_screenshot(str(screenshot_path))
            
            # Save HTML if configured
            if self.config.system_config.save_html:
                html_path = self.output_dir / 'html' / f"{row['Property ID']}.html"
                html_path.parent.mkdir(exist_ok=True)
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
            
        finally:
            if driver:
                driver.quit()
        
        return extracted_data
    
    def process_batch(self, 
                     start_idx: int = 0, 
                     batch_size: Optional[int] = None,
                     parallel: bool = False) -> List[ExtractionResult]:
        """Process a batch of properties"""
        batch_size = batch_size or self.config.system_config.batch_size
        end_idx = min(start_idx + batch_size, len(self.df))
        
        batch_df = self.df.iloc[start_idx:end_idx]
        results = []
        
        if parallel and self.config.system_config.max_workers > 1:
            # Parallel processing
            with ThreadPoolExecutor(max_workers=self.config.system_config.max_workers) as executor:
                futures = {
                    executor.submit(self.extract_property, row): idx
                    for idx, row in batch_df.iterrows()
                }
                
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=60)
                        results.append(result)
                        self._log_progress(len(results), len(batch_df))
                    except Exception as e:
                        logger.error(f"Error in parallel extraction: {e}")
        else:
            # Sequential processing
            for idx, row in batch_df.iterrows():
                result = self.extract_property(row)
                results.append(result)
                self._log_progress(len(results), len(batch_df))
                
                # Rate limiting
                domain = urlparse(row.get('Tax Bill Link', '')).netloc
                if scraper_config := self.config.get_scraper_config(domain):
                    time.sleep(scraper_config.rate_limit_delay)
        
        self.results.extend(results)
        
        # Save intermediate results if configured
        if self.config.system_config.save_intermediate:
            self._save_intermediate_results(start_idx, end_idx)
        
        return results
    
    def process_all(self, parallel: bool = False) -> List[ExtractionResult]:
        """Process all properties"""
        logger.info(f"Starting extraction of {len(self.df)} properties")
        
        batch_size = self.config.system_config.batch_size
        total_batches = (len(self.df) + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            logger.info(f"Processing batch {batch_num + 1}/{total_batches}")
            
            self.process_batch(start_idx, batch_size, parallel)
        
        logger.info(f"Extraction complete. Processed {len(self.results)} properties")
        return self.results
    
    def _log_progress(self, current: int, total: int):
        """Log extraction progress"""
        percentage = (current / total) * 100
        if current % 10 == 0 or current == total:
            logger.info(f"Progress: {current}/{total} ({percentage:.1f}%)")
    
    def _save_intermediate_results(self, start_idx: int, end_idx: int):
        """Save intermediate results to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"intermediate_results_{start_idx}_{end_idx}_{timestamp}.json"
        filepath = self.output_dir / 'intermediate' / filename
        filepath.parent.mkdir(exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(
                [r.to_dict() for r in self.results[-end_idx+start_idx:]],
                f,
                indent=2,
                default=str
            )
        
        logger.debug(f"Saved intermediate results to {filepath}")
    
    def save_results(self, output_file: str = 'robust_extraction_results.xlsx'):
        """Save extraction results to Excel with multiple sheets"""
        if not self.results:
            logger.warning("No results to save")
            return
        
        # Convert results to DataFrame
        results_df = pd.DataFrame([r.to_dict() for r in self.results])
        
        # Create summary statistics
        summary_stats = self._generate_summary_stats()
        
        # Create validation report
        validation_report = self._generate_validation_report()
        
        # Create error report
        error_report = pd.DataFrame(self.error_handler.error_history)
        
        # Save to Excel with multiple sheets
        output_path = self.output_dir / output_file
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            results_df.to_excel(writer, sheet_name='Extraction Results', index=False)
            summary_stats.to_excel(writer, sheet_name='Summary Statistics', index=False)
            validation_report.to_excel(writer, sheet_name='Validation Report', index=False)
            
            if not error_report.empty:
                error_report.to_excel(writer, sheet_name='Error Log', index=False)
        
        logger.info(f"Results saved to {output_path}")
        
        # Also save as JSON for programmatic access
        json_path = output_path.with_suffix('.json')
        with open(json_path, 'w') as f:
            json.dump(
                {
                    'results': [r.to_dict() for r in self.results],
                    'summary': summary_stats.to_dict('records'),
                    'validation': validation_report.to_dict('records'),
                    'errors': self.error_handler.get_error_summary()
                },
                f,
                indent=2,
                default=str
            )
        
        logger.info(f"JSON results saved to {json_path}")
    
    def _generate_summary_stats(self) -> pd.DataFrame:
        """Generate summary statistics"""
        stats = []
        
        # Overall statistics
        total_properties = len(self.results)
        successful = sum(1 for r in self.results if r.extraction_status == 'success')
        failed = sum(1 for r in self.results if r.extraction_status == 'failed')
        
        stats.append({
            'Metric': 'Total Properties',
            'Value': total_properties
        })
        stats.append({
            'Metric': 'Successful Extractions',
            'Value': f"{successful} ({successful/total_properties*100:.1f}%)"
        })
        stats.append({
            'Metric': 'Failed Extractions',
            'Value': f"{failed} ({failed/total_properties*100:.1f}%)"
        })
        
        # Status breakdown
        status_counts = {}
        for result in self.results:
            status = result.extraction_status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in sorted(status_counts.items()):
            stats.append({
                'Metric': f"Status: {status}",
                'Value': f"{count} ({count/total_properties*100:.1f}%)"
            })
        
        # Domain breakdown
        domain_counts = {}
        for result in self.results:
            if result.source_domain:
                domain_counts[result.source_domain] = domain_counts.get(result.source_domain, 0) + 1
        
        for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            stats.append({
                'Metric': f"Domain: {domain}",
                'Value': count
            })
        
        # Field extraction rates
        field_counts = {
            'property_address': 0,
            'account_number': 0,
            'amount_due': 0,
            'previous_year_taxes': 0,
            'next_due_date': 0
        }
        
        for result in self.results:
            if result.extraction_status == 'success':
                for field in field_counts:
                    if getattr(result, field, None) is not None:
                        field_counts[field] += 1
        
        for field, count in field_counts.items():
            if successful > 0:
                stats.append({
                    'Metric': f"Field: {field}",
                    'Value': f"{count}/{successful} ({count/successful*100:.1f}%)"
                })
        
        # Performance metrics
        avg_duration = sum(r.extraction_duration or 0 for r in self.results) / len(self.results)
        max_duration = max((r.extraction_duration or 0 for r in self.results), default=0)
        total_retries = sum(r.retry_count for r in self.results)
        
        stats.append({'Metric': 'Average Extraction Time', 'Value': f"{avg_duration:.2f} seconds"})
        stats.append({'Metric': 'Max Extraction Time', 'Value': f"{max_duration:.2f} seconds"})
        stats.append({'Metric': 'Total Retries', 'Value': total_retries})
        
        return pd.DataFrame(stats)
    
    def _generate_validation_report(self) -> pd.DataFrame:
        """Generate validation report"""
        report_data = []
        
        for result in self.results:
            if result.validation_issues:
                report_data.append({
                    'Property ID': result.property_id,
                    'Property Name': result.property_name,
                    'Validation Status': result.validation_status,
                    'Issues': ', '.join(result.validation_issues),
                    'Extraction Status': result.extraction_status
                })
        
        if not report_data:
            report_data.append({
                'Property ID': 'N/A',
                'Property Name': 'No validation issues found',
                'Validation Status': 'all_valid',
                'Issues': '',
                'Extraction Status': ''
            })
        
        return pd.DataFrame(report_data)

def main():
    """Main execution function"""
    logger.info("Starting Robust Tax Extractor")
    
    # Initialize extractor
    extractor = RobustTaxExtractor('phase-two-taxes-8-17.xlsx')
    
    # Validate configuration
    if not extractor.config.validate_config():
        logger.error("Invalid configuration. Please check config.json")
        return
    
    # Process all properties
    results = extractor.process_all(parallel=False)
    
    # Save results
    extractor.save_results()
    
    # Print summary
    print("\n" + "="*60)
    print("EXTRACTION COMPLETE")
    print("="*60)
    
    status_counts = {}
    for result in results:
        status = result.extraction_status
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print(f"Total Properties: {len(results)}")
    print("\nStatus Breakdown:")
    for status, count in sorted(status_counts.items()):
        percentage = (count / len(results)) * 100
        print(f"  {status}: {count} ({percentage:.1f}%)")
    
    # Print error summary if any
    error_summary = extractor.error_handler.get_error_summary()
    if error_summary['total_errors'] > 0:
        print(f"\nTotal Errors: {error_summary['total_errors']}")
        print("Error Types:")
        for error_type, count in error_summary['error_counts'].items():
            print(f"  {error_type}: {count}")
    
    print(f"\nResults saved to: {extractor.output_dir}")
    print("Check robust_extraction_results.xlsx for detailed results")
    
    logger.info("Extraction process completed successfully")

if __name__ == "__main__":
    main()